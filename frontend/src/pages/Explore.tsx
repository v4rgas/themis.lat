import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { EmbeddingAtlas } from "embedding-atlas/react"
import { Coordinator, wasmConnector } from '@uwdata/vgplot'
import { loadParquet } from '@uwdata/mosaic-sql'
import { useTheme } from '../context/ThemeContext'

export function Explore() {
  const { theme } = useTheme()
  const navigate = useNavigate()
  const [coordinator, setCoordinator] = useState<Coordinator | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedData, setSelectedData] = useState<any[] | null>(null)
  const [selectionPredicate, setSelectionPredicate] = useState<string | null>(null)


  useEffect(() => {
    async function init() {
      try {
        // Create coordinator and connect to DuckDB-WASM
        const coord = new Coordinator()
        coord.databaseConnector(wasmConnector())

        // Load parquet file into DuckDB
        // Use fetch to get the file URL that works with Vite's dev server
        await coord.exec([
          loadParquet("data", `${window.location.origin}/data/lic_2020-1_umap.parquet`)
        ])

        // Add unique row ID (CodigoExterno has duplicates)
        await coord.exec("ALTER TABLE data ADD COLUMN _row_id INTEGER")
        await coord.exec("UPDATE data SET _row_id = rowid")

        // Add category column based on MontoEstimado ranges
        await coord.exec("ALTER TABLE data ADD COLUMN _category VARCHAR")
        await coord.exec(`
          UPDATE data
          SET _category = CASE
            WHEN MontoEstimado IS NULL THEN 'Unknown'
            WHEN MontoEstimado < 1000000 THEN '< $1M'
            WHEN MontoEstimado < 5000000 THEN '$1M - $5M'
            WHEN MontoEstimado < 10000000 THEN '$5M - $10M'
            WHEN MontoEstimado < 50000000 THEN '$10M - $50M'
            WHEN MontoEstimado < 100000000 THEN '$50M - $100M'
            WHEN MontoEstimado < 500000000 THEN '$100M - $500M'
            ELSE '> $500M'
          END
        `)

        // Get table info to find columns
        const result = await coord.query("DESCRIBE data")
        console.log("Table schema:", result)

        setCoordinator(coord)
        setLoading(false)
      } catch (err) {
        console.error("Failed to initialize:", err)
        setError(err instanceof Error ? err.message : String(err))
        setLoading(false)
      }
    }

    init()
  }, [])

  if (loading) {
    return (
      <div className="app loading-screen">
        <div className="loader"></div>
        <p className="loading-text">Calculando...</p>
      </div>
    )
  }

  if (error) {
    return <div className="app">Error: {error}</div>
  }

  if (!coordinator) {
    return <div className="app">Failed to initialize coordinator</div>
  }

  const handleViewDetails = () => {
    if (selectedData && selectedData.length === 1) {
      // Navigate to detail page with the selected node data
      navigate('/detail', { state: { nodeData: selectedData[0] } })
    }
  }

  return (
    <div className="app">
      {selectedData && selectedData.length === 1 && (
        <div style={{
          position: 'fixed',
          top: '24px',
          right: '24px',
          zIndex: 1000,
          background: 'var(--bg-secondary)',
          padding: '20px 24px',
          borderRadius: '12px',
          boxShadow: `0 8px 32px var(--shadow-color)`,
          backdropFilter: 'blur(10px)',
          border: '1px solid var(--shadow-color)',
          minWidth: '280px',
          animation: 'slideIn 0.3s ease-out',
          fontFamily: 'system-ui, -apple-system, sans-serif'
        }}>
          <div style={{
            fontSize: '13px',
            color: 'var(--text-secondary)',
            marginBottom: '8px',
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
            fontWeight: '600',
            fontFamily: 'system-ui, -apple-system, sans-serif'
          }}>
            Licitación seleccionada
          </div>
          <div style={{
            fontSize: '15px',
            fontWeight: '600',
            color: 'var(--text-primary)',
            marginBottom: '16px',
            lineHeight: '1.4',
            wordBreak: 'break-word',
            fontFamily: 'system-ui, -apple-system, sans-serif'
          }}>
            {selectedData[0].tender_name || selectedData[0].CodigoExterno}
          </div>
          <button
            onClick={handleViewDetails}
            style={{
              width: '100%',
              padding: '12px 20px',
              background: 'var(--accent-primary)',
              color: 'var(--accent-text)',
              border: 'none',
              borderRadius: '8px',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: '600',
              transition: 'all 0.2s ease',
              boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)',
              letterSpacing: '0.3px',
              fontFamily: 'system-ui, -apple-system, sans-serif'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = 'translateY(-2px)'
              e.currentTarget.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.15)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'translateY(0)'
              e.currentTarget.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.1)'
            }}
          >
            Analizar licitación
          </button>
        </div>
      )}
      <style>{`
        @keyframes slideIn {
          from {
            opacity: 0;
            transform: translateX(20px);
          }
          to {
            opacity: 1;
            transform: translateX(0);
          }
        }
      `}</style>
      <EmbeddingAtlas
        coordinator={coordinator}
        colorScheme={theme}
        data={{
          table: "data",
          id: "_row_id",
          projection: { x: "x", y: "y" },
          text: "tender_name"
        }}
        initialState={{
          version: "0.13.0",
          timestamp: Date.now(),
          charts: {
            "embedding": {
              type: "embedding",
              title: "Embedding View",
              data: {
                x: "x",
                y: "y",
                category: "_category",
                text: "CodigoExterno"
              }
            },
            "predicates": {
              type: "predicates",
              title: "SQL Filters",
              items: [
                {
                  name: "Quick Award (<150 days)",
                  predicate: "date_diff('day', first_activity_date, FechaAdjudicacion) < 150"
                },
                {
                  name: "High Daily Award Rate",
                  predicate: "MontoLineaAdjudica/date_diff('day', first_activity_date, FechaAdjudicacion)>1000000"
                },
                {
                  name: "High Daily Award Rate (from Publication)",
                  predicate: "MontoLineaAdjudica/date_diff('day', FechaPublicacion, FechaAdjudicacion)>1000000"
                }
              ]
            }
          }
        }}
        onStateChange={async (state) => {
          console.log("========== STATE CHANGE ==========")
          console.log("Full state:", state)
          console.log("Selection predicate:", state.predicate)
          console.log("Predicate type:", typeof state.predicate)
          console.log("==================================")

          // Update selection predicate
          setSelectionPredicate(state.predicate || null)

          // Query selected data if there's a selection
          if (state.predicate && coordinator) {
            try {
              console.log("Querying with predicate:", state.predicate)
              const result = await coordinator.query(
                `SELECT * FROM data WHERE ${state.predicate}`
              )
              console.log("Query result:", result)
              console.log("Result type:", typeof result)

              const dataArray = result ? Array.from(result) : null
              console.log("Data array:", dataArray)
              console.log("Data array length:", dataArray?.length)

              setSelectedData(dataArray)
            } catch (err) {
              console.error("Failed to query selection:", err)
              setSelectedData(null)
            }
          } else {
            console.log("No predicate, clearing selection")
            setSelectedData(null)
          }
        }}
        chartTheme={{
          scheme: theme,
          categoryColors: () => {
            // Color scale for MontoEstimado ranges (low to high)
            return [
              '#808080', // NULL/Unknown
              '#2ecc71', // < 1M
              '#3498db', // 1M-5M
              '#9b59b6', // 5M-10M
              '#f39c12', // 10M-50M
              '#e67e22', // 50M-100M
              '#e74c3c', // 100M-500M
              '#c0392b'  // > 500M
            ]
          }
        }}
        embeddingViewConfig={{
          autoLabelEnabled: false
        }}
      />
    </div>
  )
}
