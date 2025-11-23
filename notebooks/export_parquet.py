import pandas as pd
from sklearn.preprocessing import StandardScaler
from umap import UMAP
from openTSNE import TSNE
from sentence_transformers import SentenceTransformer
import numpy as np
from tqdm import tqdm
from glob import glob
from typing import Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp

df_act = pd.read_csv("downloads/PUB_EMPRESAS_PJ_2020_A_2024.txt", sep="\t")
# Año comercial	RUT	DV	Razón social	Tramo según ventas
# Número de trabajadores dependie	Fecha inicio de actividades vige	Fecha término de giro
# Fecha primera inscripción de ac	Tipo término de giro
# Tipo de contribuyente	Subtipo de contribuyente	Tramo capital propio positivo	Tramo capital propio negativo
# Rubro económico	Subrubro económico	Actividad económica
# Región	Provincia	Comuna
# R_PRESUNTA	OTROS_REGIMENES
df_act.columns = [
    "fiscal_year",
    "rut",
    "dv",
    "company_name",
    "sales_bracket",
    "num_employees",
    "current_activity_start_date",
    "activity_end_date",
    "first_registration_date",
    "activity_end_type",
    "contributor_type",
    "contributor_subtype",
    "positive_equity_bracket",
    "negative_equity_bracket",
    "economic_sector",
    "economic_subsector",
    "economic_activity",
    "region",
    "province",
    "commune",
    "presumed_income",
    "other_regimes",
]
# Note: We'll use safe_to_datetime for dates in the processing function
# For df_act, we use errors="coerce" and let safe_to_datetime handle invalid dates later
df_act.first_registration_date = pd.to_datetime(
    df_act.first_registration_date, errors="coerce"
)
df_act.current_activity_start_date = pd.to_datetime(
    df_act.current_activity_start_date, errors="coerce"
)
df_act.activity_end_date = pd.to_datetime(df_act.activity_end_date, errors="coerce")

rut_to_registration_date = {
    str(d["rut"]): d["first_registration_date"]
    for d in df_act[["rut", "first_registration_date"]].to_dict(orient="records")
}

# Model will be initialized in each worker process
_model_cache = None


def get_model():
    """Lazy load model (one per process)."""
    global _model_cache
    if _model_cache is None:
        _model_cache = SentenceTransformer("all-MiniLM-L6-v2")
    return _model_cache


def safe_to_datetime(series, fallback_date="1900-01-01"):
    """
    Safely convert a series to datetime, using fallback_date for invalid dates.
    Handles out-of-bounds dates and other parsing errors.
    """
    try:
        from pandas._libs.tslibs.np_datetime import OutOfBoundsDatetime
    except ImportError:
        # OutOfBoundsDatetime might not be available in all pandas versions
        OutOfBoundsDatetime = ValueError

    fallback = pd.Timestamp(fallback_date)
    min_date = pd.Timestamp("1677-09-21")
    max_date = pd.Timestamp("2262-04-11")

    # Use element-wise conversion to catch OutOfBoundsDatetime errors
    result = pd.Series(index=series.index, dtype="datetime64[ns]")
    for idx, val in series.items():
        try:
            # Skip NaN values
            if pd.isna(val):
                result.loc[idx] = fallback
                continue
            # Try to parse
            parsed = pd.to_datetime(val, errors="coerce")
            if pd.isna(parsed):
                result.loc[idx] = fallback
            elif parsed < min_date or parsed > max_date:
                result.loc[idx] = fallback
            else:
                result.loc[idx] = parsed
        except (ValueError, OverflowError, OutOfBoundsDatetime):
            # Catch any date parsing errors (including OutOfBoundsDatetime) and use fallback
            result.loc[idx] = fallback
    return result


def format_text_for_embedding(row):
    return "\n\n".join(
        [
            (row["Nombre"] if not pd.isna(row["Nombre"]) else ""),
            (row["Descripcion"] if not pd.isna(row["Descripcion"]) else ""),
            (
                row["Nombre producto genrico"]
                if not pd.isna(row["Nombre producto genrico"])
                else ""
            ),
            (
                row["Descripcion linea Adquisicion"]
                if not pd.isna(row["Descripcion linea Adquisicion"])
                else ""
            ),
            (
                row["DescripcionProveedor"]
                if not pd.isna(row["DescripcionProveedor"])
                else ""
            ),
        ]
    )


def identify_numeric_columns(df):
    """Identify numeric columns in a dataframe."""
    numeric_columns = []
    for col in df.columns:
        if col in (
            "CodigoExterno",
            "Codigo",
            "CodigoEstado",
            "EstadoEtapas",
            "CodigoUnidad",
            "Informada",
            "EsBaseTipo",
            "ValorTiempoRenovacion",
            "EsRenovable",
            "Codigoitem",
            "CodigoProductoONU",
            "CodigoSucursalProveedor",
            "Correlativo",
        ):
            continue
        # Try to convert to numeric, handling comma decimal separators
        # Replace comma with dot for decimal separator
        test_series = df[col].astype(str).str.replace(",", ".", regex=False)
        numeric_series = pd.to_numeric(test_series, errors="coerce")
        # Check if column is numeric (has valid numeric values and not all NaN)
        if numeric_series.notna().any():
            # Check if the column is actually numeric (most values are numeric)
            non_null_count = numeric_series.notna().sum()
            total_count = len(numeric_series)
            # Consider it numeric if at least 50% of values are numeric
            if non_null_count / total_count >= 0.5:
                numeric_columns.append(col)
    return numeric_columns


def get_all_numeric_columns(csv_files):
    """Scan all CSV files to identify the union of all numeric columns."""
    all_numeric_columns = set()
    print("Scanning all CSV files to identify numeric columns...")
    for file_path in tqdm(csv_files, desc="Scanning files"):
        try:
            df = pd.read_csv(
                file_path, encoding="latin-1", sep=";", nrows=1000
            )  # Sample first 1000 rows for speed
            numeric_cols = identify_numeric_columns(df)
            all_numeric_columns.update(numeric_cols)
        except Exception as e:
            print(f"Warning: Error scanning {file_path}: {e}")
            continue
    # Convert to sorted list for consistency
    numeric_columns_list = sorted(list(all_numeric_columns))
    print(f"Found {len(numeric_columns_list)} numeric columns across all files")
    return numeric_columns_list


def process_and_embed_one_file(
    file_path, numeric_columns: list, rut_to_registration_date: dict
) -> Tuple[pd.DataFrame, np.ndarray]:
    """Process a single file and return result_df and combined_features."""
    print(f"Processing file: {file_path}")
    # Load model in this process
    model = get_model()
    # Load CSV with latin-1 encoding and semicolon separator
    df = (
        pd.read_csv(file_path, encoding="latin-1", sep=";")
        .sample(frac=0.2)
        .reset_index(drop=True)
    )

    # Prepare numeric data for UMAP
    # Ensure all required numeric columns exist, fill missing ones with 0
    numeric_data = pd.DataFrame(index=df.index)
    for col in numeric_columns:
        if col in df.columns:
            numeric_data[col] = df[col]
        else:
            numeric_data[col] = 0

    # Convert to numeric, handling comma decimal separators
    for col in numeric_columns:
        # Replace comma with dot for decimal separator, then convert to numeric
        numeric_data[col] = (
            numeric_data[col].astype(str).str.replace(",", ".", regex=False)
        )
        numeric_data[col] = pd.to_numeric(numeric_data[col], errors="coerce")
    # Fill missing values with 0 (or could use median/mean)
    numeric_data = numeric_data.fillna(0)
    # Ensure all values are float (not object/string)
    numeric_data = numeric_data.astype(float).drop_duplicates()

    # Filter for awards (CantidadAdjudicada > 0)
    if "CantidadAdjudicada" not in numeric_data.columns:
        print(
            f"Warning: CantidadAdjudicada not found in numeric columns for {file_path}, skipping awards filter"
        )
        numeric_data_only_awards = numeric_data.drop_duplicates()
    else:
        numeric_data_only_awards = numeric_data[
            numeric_data["CantidadAdjudicada"] > 0
        ].drop_duplicates()
    df_awards = df.iloc[numeric_data_only_awards.index].copy()

    df_awards.loc[:, "compiled_text"] = df_awards.apply(
        format_text_for_embedding, axis=1
    )
    df_awards.loc[:, "supplier_rut"] = df_awards["RutProveedor"].map(
        lambda x: x.split("-")[0].replace(".", "")
    )

    # Get compiled_text for awards data (matching the indices)
    texts = df_awards["compiled_text"].fillna("").tolist()

    # Compute embeddings efficiently in batches
    print(f"Computing embeddings for {len(texts)} texts in {file_path}...")
    text_embeddings = model.encode(
        texts, batch_size=16, show_progress_bar=False, convert_to_numpy=True
    )

    print(f"Text embeddings shape: {text_embeddings.shape}")
    print(f"Embedding dimension: {text_embeddings.shape[1]}")

    # Concatenate text embeddings with numeric columns
    # Ensure numeric_data_only_awards is aligned with text_embeddings
    numeric_array = numeric_data_only_awards.values.astype(np.float32)

    # Check for and handle infinite values
    if np.any(np.isinf(numeric_array)):
        print("Warning: Found infinite values, replacing with NaN")
        numeric_array = np.where(np.isinf(numeric_array), np.nan, numeric_array)

    # Replace any remaining NaN with 0
    numeric_array = np.nan_to_num(numeric_array, nan=0.0, posinf=0.0, neginf=0.0)

    # Concatenate text embeddings (text_embeddings) with numeric columns (numeric_array)
    # Result: (n_samples, embedding_dim + n_numeric_features)
    combined_features = np.concatenate([text_embeddings, numeric_array], axis=1)

    print(f"Combined features shape: {combined_features.shape}")
    print(f"  - Text embedding dimension: {text_embeddings.shape[1]}")
    print(f"  - Numeric columns dimension: {numeric_array.shape[1]}")
    print(f"  - Total dimension: {combined_features.shape[1]}")

    df_awards.loc[:, "first_activity_date"] = df_awards["supplier_rut"].map(
        rut_to_registration_date.get
    )

    # Create final DataFrame with CodigoExterno, numeric columns (without UMAP x, y)
    result_df = pd.DataFrame()
    result_df["CodigoExterno"] = df_awards["CodigoExterno"]
    result_df["tender_name"] = df_awards["Nombre"]
    result_df["supplier_name"] = df_awards["RazonSocialProveedor"]
    result_df["supplier_rut"] = df_awards["supplier_rut"]
    result_df["first_activity_date"] = safe_to_datetime(
        df_awards["first_activity_date"]
    )

    for col in df_awards.columns:
        if col.startswith("Fecha"):
            result_df[col] = safe_to_datetime(df_awards[col])
    # Add all numeric columns
    for col in numeric_columns:
        result_df[col] = numeric_data_only_awards[col]
    result_df.reset_index(drop=True, inplace=True)
    # Display result
    print(f"Shape: {result_df.shape}")
    print(f"Numeric columns found: {len(numeric_columns)}")
    print(f"Columns: {list(result_df.columns[:5])}... (showing first 5)")

    return result_df, combined_features


# Main processing
if __name__ == "__main__":
    # Find all CSV files matching the pattern
    csv_files = sorted(glob("downloads/lic_*.csv"))
    if not csv_files:
        print("No CSV files found matching downloads/lic_*.csv")
        exit(1)

    print(f"Found {len(csv_files)} CSV files to process")

    # First pass: identify all numeric columns across all files
    all_numeric_columns = get_all_numeric_columns(csv_files)

    # Process each file in parallel and collect results
    all_result_dfs = []
    all_combined_features = []

    print("\nProcessing files and computing embeddings in parallel...")
    max_workers = min(24, len(csv_files), mp.cpu_count())
    print(f"Using {max_workers} worker processes")

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_file = {
            executor.submit(
                process_and_embed_one_file,
                file_path,
                all_numeric_columns,
                rut_to_registration_date,
            ): file_path
            for file_path in csv_files
        }

        # Collect results as they complete
        for future in tqdm(
            as_completed(future_to_file), total=len(csv_files), desc="Processing files"
        ):
            file_path = future_to_file[future]
            try:
                result_df, combined_features = future.result()
                all_result_dfs.append(result_df)
                all_combined_features.append(combined_features)
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                import traceback

                traceback.print_exc()
                continue

    if not all_result_dfs:
        print("No files were successfully processed")
        exit(1)

    # Concatenate all result DataFrames
    print("\nConcatenating all result DataFrames...")
    final_result_df = pd.concat(all_result_dfs, ignore_index=True)
    print(f"Final result DataFrame shape: {final_result_df.shape}")

    # Concatenate all combined features
    print("\nConcatenating all combined features...")
    all_combined_features_array = np.concatenate(all_combined_features, axis=0)
    print(f"Combined features array shape: {all_combined_features_array.shape}")

    # Apply global normalization to numeric features only (text embeddings are already normalized)
    # Split features: text embeddings (first 384 cols) and numeric features (last 33 cols)
    text_embedding_dim = 384
    numeric_feature_dim = all_combined_features_array.shape[1] - text_embedding_dim

    print(f"\nApplying global normalization to numeric features...")
    print(f"  - Text embedding columns: 0-{text_embedding_dim - 1} (keeping as-is)")
    print(
        f"  - Numeric feature columns: {text_embedding_dim}-{all_combined_features_array.shape[1] - 1} (normalizing)"
    )

    # Extract numeric features (last numeric_feature_dim columns)
    numeric_features = all_combined_features_array[:, text_embedding_dim:]

    # Normalize numeric features globally
    scaler = StandardScaler()
    numeric_features_normalized = scaler.fit_transform(numeric_features).astype(
        np.float32
    )

    # Reconstruct combined features with normalized numeric part
    all_combined_features_array = np.concatenate(
        [
            all_combined_features_array[:, :text_embedding_dim],
            numeric_features_normalized,
        ],
        axis=1,
    )
    print(f"Global normalization complete. Feature statistics:")
    print(
        f"  - Text embeddings: mean={all_combined_features_array[:, :text_embedding_dim].mean():.4f}, std={all_combined_features_array[:, :text_embedding_dim].std():.4f}"
    )
    print(
        f"  - Numeric features: mean={numeric_features_normalized.mean():.4f}, std={numeric_features_normalized.std():.4f}"
    )

    # Check for duplicate rows (can cause issues with nearest neighbor search)
    # Add tiny random noise to duplicate rows to make them unique
    print("\nChecking for duplicate rows...")
    unique_rows, unique_indices, inverse_indices = np.unique(
        all_combined_features_array, axis=0, return_index=True, return_inverse=True
    )
    if len(unique_rows) < len(all_combined_features_array):
        print(
            f"Warning: Found {len(all_combined_features_array) - len(unique_rows)} duplicate rows, adding small noise"
        )
        # Add very small random noise to make duplicates unique
        np.random.seed(42)
        noise = np.random.normal(0, 1e-8, all_combined_features_array.shape).astype(
            np.float32
        )
        all_combined_features_array = all_combined_features_array + noise

    X_embedded_tsne = TSNE(n_components=2, perplexity=50, n_jobs=-1).fit(
        all_combined_features_array
    )

    output_path_tsne = "downloads/all_months_tsne_gpu.parquet"
    print(f"\nSaving final result to {output_path_tsne}...")
    final_result_df["x"] = X_embedded_tsne[:, 0]
    final_result_df["y"] = X_embedded_tsne[:, 1]
    final_result_df.to_parquet(output_path_tsne)

    print(f"\nCompleted! Final dataset shape: {final_result_df.shape}")
    print(f"Columns: {list(final_result_df.columns)}")
