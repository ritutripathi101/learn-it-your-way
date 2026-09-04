import { useState } from 'react'

function App() {
  const [result, setResult] = useState(null)

  const handleFileChange = async (event) => {
    const file = event.target.files[0]
    if (!file) return

    const formData = new FormData()
    formData.append('file', file)

    const response = await fetch('http://localhost:8000/upload', {
      method: 'POST',
      body: formData,
    })
    const data = await response.json()
    setResult(data)
  }

  return (
    <div style={{ padding: '2rem' }}>
      <h1>Learn It Your Way</h1>
      <input type="file" onChange={handleFileChange} />
      {result && (
        <p>Uploaded: {result.filename} ({result.size_bytes} bytes)</p>
      )}
    </div>
  )
}

export default App