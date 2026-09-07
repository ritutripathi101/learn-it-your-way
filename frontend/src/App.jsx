import { useState } from 'react'

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
        minHeight: '60px',
        transition: 'background 0.2s ease',
      }}
    >
      {!flipped ? (
        <p><strong>Q:</strong> {question}</p>
      ) : (
        <p><strong>A:</strong> {answer}</p>
      )}
      <p style={{ fontSize: '0.75rem', color: '#888', marginTop: '0.5rem' }}>
        {flipped ? 'Click to see question' : 'Click to reveal answer'}
      </p>
    </div>
  )
}

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
    <div style={{ padding: '2rem', fontFamily: 'sans-serif', maxWidth: '700px', margin: '0 auto' }}>
      <h1>Learn It Your Way</h1>
      <p>Upload a lecture slide deck (PDF or PPTX) to generate flashcards.</p>

      <input type="file" onChange={handleFileChange} accept=".pdf,.pptx" />

      {loading && <p>Uploading and generating flashcards...</p>}

      {result && (
        <div style={{ marginTop: '1rem' }}>
          <p><strong>Uploaded:</strong> {result.filename}</p>

          {result.error ? (
            <p style={{ color: 'red' }}>{result.error}</p>
          ) : (
            <div>
              <h2>Flashcards ({result.flashcards.length})</h2>
              {result.flashcards.map((card, index) => (
                <FlashCard key={index} question={card.question} answer={card.answer} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default App