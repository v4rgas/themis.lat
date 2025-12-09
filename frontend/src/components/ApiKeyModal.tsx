import { useState, useRef, useEffect } from "react";
import "./ApiKeyModal.css";

interface ApiKeyModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (apiKey: string) => void;
}

export function ApiKeyModal({ isOpen, onClose, onSubmit }: ApiKeyModalProps) {
  const [apiKey, setApiKey] = useState(() => {
    // Try to load from sessionStorage
    return sessionStorage.getItem("openrouter_api_key") || "";
  });
  const [error, setError] = useState("");
  const dialogRef = useRef<HTMLDialogElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen && dialogRef.current) {
      dialogRef.current.showModal();
      // Focus the input after a short delay to ensure dialog is rendered
      setTimeout(() => inputRef.current?.focus(), 100);
    } else if (!isOpen && dialogRef.current) {
      dialogRef.current.close();
    }
  }, [isOpen]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!apiKey.trim()) {
      setError("API key is required");
      return;
    }

    if (!apiKey.startsWith("sk-or-")) {
      setError("Invalid OpenRouter API key format (should start with sk-or-)");
      return;
    }

    // Save to sessionStorage
    sessionStorage.setItem("openrouter_api_key", apiKey);
    setError("");
    onSubmit(apiKey);
  };

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === dialogRef.current) {
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <dialog
      ref={dialogRef}
      className="api-key-modal"
      onClick={handleBackdropClick}
    >
      <div className="api-key-modal-content" onClick={(e) => e.stopPropagation()}>
        <button className="api-key-modal-close" onClick={onClose}>
          ✕
        </button>

        <h2 className="api-key-modal-title">OpenRouter API Key</h2>

        <p className="api-key-modal-description">
          Enter your OpenRouter API key to start the investigation.
          Your key is stored in session storage and never sent to our servers.
        </p>

        <form onSubmit={handleSubmit}>
          <div className="api-key-input-group">
            <label htmlFor="apiKey" className="api-key-label">
              API Key
            </label>
            <input
              ref={inputRef}
              type="password"
              id="apiKey"
              className={`api-key-input ${error ? "error" : ""}`}
              placeholder="sk-or-v1-..."
              value={apiKey}
              onChange={(e) => {
                setApiKey(e.target.value);
                setError("");
              }}
              autoComplete="off"
            />
            {error && <span className="api-key-error">{error}</span>}
          </div>

          <div className="api-key-modal-actions">
            <button type="button" className="api-key-btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="api-key-btn-primary">
              Start Investigation
            </button>
          </div>
        </form>

        <a
          href="https://openrouter.ai/keys"
          target="_blank"
          rel="noopener noreferrer"
          className="api-key-link"
        >
          Get an API key from OpenRouter →
        </a>
      </div>
    </dialog>
  );
}
