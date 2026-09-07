import { useState, useEffect, useRef } from 'react'
import mermaid from 'mermaid'

mermaid.initialize({ startOnLoad: false })

function FlashCard({ question, answer }) {
  const [flipped, setFlipped] = useState(false)
  return (
    <div
      onClick={() => setFlipped(!flipped)}
      style={{
        background: flipped ? '#dff5e1' : '#f4f4f4',
        padding: '1.25rem',
        borderRadius: '10px',
        marginBottom: '0.75rem',
        cursor: 'pointer',
      }}
    >
      {!flipped ? <p><strong>Q:</strong> {question}</p> : <p><strong>A:</strong> {answer}</p>}
      <p style={{ fontSize: '0.75rem', color: '#888', marginTop: '0.5rem' }}>
        {flipped ? 'Click to see question' : 'Click to reveal answer'}
      </p>
    </div>
  )
}

function ConceptMap({ diagram }) {
  const ref = useRef(null)

  useEffect(() => {
    if (diagram && ref.current) {
      mermaid.render('concept-map-svg', diagram).then(({ svg }) => {
        ref.current.innerHTML = svg
      }).catch((err) => {
        ref.current.innerHTML = `<p style="color:red">Couldn't render diagram: ${err.message}</p>`
      })
    }
  }, [diagram])

  return <div ref={ref} style={{ overflowX: 'auto' }} />
}

function App() {
  const [mode, setMode] = useState('flashcards') // 'flashcards' or 'map'
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const handleFileChange = async (event) => {
    const file = event.target.files[0]
    if (!file) return

    setLoading(true)
    setResult(null)

    const formData = new FormData()
    formData.append('file', file)

    const endpoint = mode === 'flashcards' ? '/upload' : '/upload-map'

    try {
      const response = await fetch(`http://localhost:8000${endpoint}`, {
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
    <div style={{ padding: '2rem', fontFamily: 'sans-serif', maxWidth: '700px', margin: '0 auto' }}>
      <h1>Learn It Your Way</h1>
      <p>Upload a lecture slide deck (PDF or PPTX) and choose how to study it.</p>

      <div style={{ marginBottom: '1rem' }}>
        <button
          onClick={() => setMode('flashcards')}
          style={{ fontWeight: mode === 'flashcards' ? 'bold' : 'normal', marginRight: '0.5rem' }}
        >
          Flashcards
        </button>
        <button
          onClick={() => setMode('map')}
          style={{ fontWeight: mode === 'map' ? 'bold' : 'normal' }}
        >
          Visual Map
        </button>
      </div>

      <input type="file" onChange={handleFileChange} accept=".pdf,.pptx" />

      {loading && <p>Uploading and generating {mode === 'flashcards' ? 'flashcards' : 'concept map'}...</p>}

      {result && (
        <div style={{ marginTop: '1rem' }}>
          <p><strong>Uploaded:</strong> {result.filename}</p>

          {result.error ? (
            <p style={{ color: 'red' }}>{result.error}</p>
          ) : mode === 'flashcards' ? (
            <div>
              <h2>Flashcards ({result.flashcards.length})</h2>
              {result.flashcards.map((card, index) => (
                <FlashCard key={index} question={card.question} answer={card.answer} />
              ))}
            </div>
          ) : (
            <div>
              <h2>Concept Map</h2>
              <ConceptMap diagram={result.diagram} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default App