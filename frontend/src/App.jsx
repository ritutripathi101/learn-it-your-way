import { useState } from 'react'

function App() {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const handleFileChange = async (event) => {
    const file = event.target.files[0]
    if (!file) return

    setLoading(true)
    setResult(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await fetch('http://localhost:8000/upload', {
        method: 'POST',
        body: formData,
      })
      const data = await response.json()
      setResult(data)
    } catch (err) {
      setResult({ error: 'Something went wrong uploading the file.' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ padding: '2rem', fontFamily: 'sans-serif' }}>
      <h1>Learn It Your Way</h1>
      <p>Upload a lecture slide deck (PDF or PPTX) to extract its content.</p>

      <input type="file" onChange={handleFileChange} accept=".pdf,.pptx" />

      {loading && <p>Uploading and extracting text...</p>}

      {result && (
        <div style={{ marginTop: '1rem' }}>
          <p><strong>Uploaded:</strong> {result.filename}</p>

          {result.error ? (
            <p style={{ color: 'red' }}>{result.error}</p>
          ) : (
            <>
              <p><strong>Total characters extracted:</strong> {result.total_characters}</p>
              <pre style={{
                whiteSpace: 'pre-wrap',
                maxWidth: '600px',
                background: '#f4f4f4',
                padding: '1rem',
                borderRadius: '8px'
              }}>
                {result.extracted_text}
              </pre>
            </>
          )}
        </div>
      )}
    </div>
  )
}

export default App