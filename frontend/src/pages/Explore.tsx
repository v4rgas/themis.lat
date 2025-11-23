import { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { EmbeddingAtlas } from "embedding-atlas/react"
import { Coordinator, wasmConnector } from '@uwdata/vgplot'
import { useTheme } from '../context/ThemeContext'

export function Explore() {
  const { theme } = useTheme()
  const navigate = useNavigate()
  const containerRef = useRef<HTMLDivElement>(null)
  const [coordinator, setCoordinator] = useState<Coordinator | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedData, setSelectedData] = useState<any[] | null>(null)
  const [downloadProgress, setDownloadProgress] = useState(0)
  const [downloadStatus, setDownloadStatus] = useState('Iniciando descarga...')

  useEffect(() => {
    async function init() {
      try {
        setDownloadStatus('Inicializando base de datos...')

        // Create coordinator and connect to DuckDB-WASM
        const coord = new Coordinator()
        const connector = wasmConnector()
        coord.databaseConnector(connector)

        // Get the DuckDB database instance
        const db = await connector.getDuckDB()

        const fileUrl = 'https://r2.themis.lat/all_months_tsne_gpu.parquet'
        const cacheName = 'parquet-files-cache'

        // Try to get the file from cache first
        const cache = await caches.open(cacheName)
        let cachedResponse = await cache.match(fileUrl)

        let allChunks: Uint8Array

        if (cachedResponse) {
          // File found in cache, use it
          setDownloadStatus('Cargando desde caché...')
          const arrayBuffer = await cachedResponse.arrayBuffer()
          allChunks = new Uint8Array(arrayBuffer)
          setDownloadProgress(100)
        } else {
          // File not in cache, download it
          const response = await fetch(fileUrl)
          if (!response.ok) {
            throw new Error(`Failed to download: ${response.statusText}`)
          }

          const contentLength = response.headers.get('content-length')
          const total = contentLength ? parseInt(contentLength, 10) : 0

          const reader = response.body?.getReader()
          if (!reader) {
            throw new Error('Failed to get response reader')
          }

          const chunks: Uint8Array[] = []
          let receivedLength = 0

          setDownloadStatus('Descargando datos...')

          while (true) {
            const { done, value } = await reader.read()

            if (done) break

            chunks.push(value)
            receivedLength += value.length

            if (total > 0) {
              const progress = Math.round((receivedLength / total) * 100)
              setDownloadProgress(progress)
              setDownloadStatus(`Descargando datos... ${progress}%`)
            }
          }

          setDownloadStatus('Procesando datos...')

          // Combine chunks into a single Uint8Array
          allChunks = new Uint8Array(receivedLength)
          let position = 0
          for (const chunk of chunks) {
            allChunks.set(chunk, position)
            position += chunk.length
          }

          // Store in cache for next time
          // Create a new ArrayBuffer to satisfy TypeScript's strict type checking
          const buffer = new ArrayBuffer(allChunks.byteLength)
          new Uint8Array(buffer).set(allChunks)
          const responseToCache = new Response(buffer, {
            headers: {
              'Content-Type': 'application/octet-stream',
              'Content-Length': allChunks.length.toString()
            }
          })
          await cache.put(fileUrl, responseToCache)
        }

        // Register the file with DuckDB's virtual filesystem
        await db.registerFileBuffer('data.parquet', allChunks)

        // Configure DuckDB settings to handle large parquet files
        await coord.exec("SET preserve_insertion_order=false")

        setDownloadStatus('Cargando datos...')

        // Load only the columns we need from the parquet file to reduce memory usage
        await coord.exec(`
          CREATE TABLE data AS
          SELECT
              *
          FROM parquet_scan('data.parquet')
        `)

        // Add unique row ID (CodigoExterno has duplicates)
        await coord.exec("ALTER TABLE data ADD COLUMN _row_id VARCHAR")
        await coord.exec("UPDATE data SET _row_id = 'SEARCHABLE_ROW_ID_'||rowid")

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

  // Super simple: on ANY click, find any element with title attribute (including Shadow DOM)
  useEffect(() => {
    if (!coordinator || !containerRef.current) return

    const handleClick = () => {
      console.log('========== CLICK DETECTED ==========')

      // Small delay to let the DOM update after click
      setTimeout(() => {
        console.log('🔍 Looking for ANY element with title attribute (including Shadow DOM)...')

        // Function to recursively search through Shadow DOMs
        const findAllWithTitle = (root: Document | ShadowRoot | Element): Element[] => {
          const elements: Element[] = []

          // Search in current root
          const found = root.querySelectorAll('[title]')
          elements.push(...Array.from(found))

          // Search in all shadow roots
          const allElements = root.querySelectorAll('*')
          allElements.forEach(el => {
            if (el.shadowRoot) {
              console.log('Found shadow root in:', el.tagName)
              elements.push(...findAllWithTitle(el.shadowRoot))
            }
          })

          return elements
        }

        // Find ALL elements with title attribute (including shadow DOM!)
        const allElementsWithTitle = findAllWithTitle(document)
        console.log('Found elements with title (including shadow DOM):', allElementsWithTitle.length)

        // Log all of them with more details
        allElementsWithTitle.forEach((el, index) => {
          const title = el.getAttribute('title')
          const tagName = el.tagName.toLowerCase()
          const classes = el.className
          console.log(`Element ${index}: <${tagName}> title="${title}" class="${classes}"`)
        })

        // Look for one that matches the SEARCHABLE_ROW_ID pattern
        // Pattern: SEARCHABLE_ROW_ID_XXXXXX (like "SEARCHABLE_ROW_ID_400086")
        const pattern = /^SEARCHABLE_ROW_ID_\d+$/

        let foundRowId: string | null = null

        for (const el of Array.from(allElementsWithTitle)) {
          const title = el.getAttribute('title')
          console.log(`Testing title "${title}" against pattern:`, title ? pattern.test(title) : false)
          if (title && pattern.test(title)) {
            foundRowId = title
            console.log('✅ Found matching row ID:', foundRowId, 'on element:', el)
            break
          }
        }

        if (foundRowId && coordinator) {
          console.log('🔵 Querying node with row ID:', foundRowId)

          // Escape single quotes to prevent SQL injection
          const escapedRowId = foundRowId.replace(/'/g, "''")

          coordinator.query(
            `SELECT * FROM data WHERE _row_id = '${escapedRowId}'`
          ).then(result => {
            const dataArray = result ? Array.from(result) : null
            console.log('📊 Query result:', dataArray)
            if (dataArray && dataArray.length > 0) {
              setSelectedData(dataArray)
            }
          }).catch(err => {
            console.error('❌ Failed to query selected node:', err)
          })
        } else {
          console.log('⚠️ No element with matching SEARCHABLE_ROW_ID pattern found - clearing selection')
          setSelectedData(null)
        }
      }, 300) // Longer delay to let DOM update
    }

    const container = containerRef.current
    container.addEventListener('click', handleClick)

    return () => {
      container.removeEventListener('click', handleClick)
    }
  }, [coordinator])

  if (loading) {
    return (
      <div className="app loading-screen">
        <div className="loader"></div>
        <p className="loading-text">{downloadStatus}</p>
        {downloadProgress > 0 && (
          <div style={{
            width: '300px',
            height: '8px',
            backgroundColor: 'rgba(255, 255, 255, 0.2)',
            borderRadius: '4px',
            overflow: 'hidden',
            marginTop: '20px'
          }}>
            <div style={{
              width: `${downloadProgress}%`,
              height: '100%',
              backgroundColor: 'var(--accent-primary)',
              transition: 'width 0.3s ease',
              borderRadius: '4px'
            }} />
          </div>
        )}
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
    <div className="app" ref={containerRef}>
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
                  name: "Proveedores reciente constitución (<30 días)",
                  predicate: "abs(date_diff('day', first_activity_date::date, coalesce(FechaAdjudicacion::date, FechaCierre::date, '1900-01-01'::date))) < 30"
                },
                {
                  name: "Adjudicación Diaria > $1M (desde inicio)",
                  predicate: "MontoLineaAdjudica/date_diff('day', first_activity_date, FechaAdjudicacion)>1000000"
                },
                {
                  name: "Adjudicación Diaria > $1M (desde publicación)",
                  predicate: "MontoLineaAdjudica/date_diff('day', FechaPublicacion, FechaAdjudicacion)>1000000"
                },
                {
                  name: "Publicación a Cierre (<5 días)",
                  predicate: "date_diff('day', FechaPublicacion, FechaCierre) < 5"
                },
                {
                  name: "Número de oferentes igual a 1",
                  predicate: "NumeroOferentes = 1"
                }
              ]
            }
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
