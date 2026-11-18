import { useEffect, useId, useRef, useState } from 'react'
import './App.css'
import RichText from './RichText.jsx'

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
const TOKEN_KEY = 'learn-it-your-way:token'
const MAX_FILE_BYTES = 20 * 1024 * 1024

async function request(path, options = {}, token = '') {
  const headers = { ...(options.headers || {}) }
  if (token) headers.Authorization = `Bearer ${token}`
  let response
  try { response = await fetch(`${API_URL}${path}`, { ...options, headers }) }
  catch { throw Object.assign(new Error('Cannot reach the server. Check your connection and try again.'), { status: 0 }) }
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = Array.isArray(payload.detail) ? 'Please check your input and try again.' : payload.detail
    throw Object.assign(new Error(detail || 'The request could not be completed. Try again.'), { status: response.status })
  }
  return payload
}

function naturalWidth(svg) {
  const box = svg.viewBox && svg.viewBox.baseVal
  return (box && box.width) || parseFloat(svg.getAttribute('width')) || 600
}

function ConceptMap({ diagram }) {
  const ref = useId()
  const [rendered, setRendered] = useState({ diagram: '', svg: '', error: '' })
  const [zoom, setZoom] = useState(1)
  const frameRef = useRef(null)
  const canvasRef = useRef(null)
  useEffect(() => {
    let cancelled = false
    import('mermaid').then(({ default: mermaid }) => {
      mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: 'neutral', themeVariables: { fontSize: '18px' }, flowchart: { htmlLabels: false, useMaxWidth: false, nodeSpacing: 40, rankSpacing: 50 } })
      return mermaid.render(`map-${ref.replace(/[^\w-]/g, '')}`, diagram)
    }).then(({ svg }) => { if (!cancelled) { setZoom(1); setRendered({ diagram, svg, error: '' }) } }).catch(() => {
      if (!cancelled) setRendered({ diagram, svg: '', error: 'This concept map could not be displayed.' })
    })
    return () => { cancelled = true }
  }, [diagram, ref])
  useEffect(() => {
    const svg = canvasRef.current?.querySelector('svg')
    if (!svg) return
    svg.removeAttribute('height')
    svg.style.maxWidth = 'none'
    svg.style.width = `${naturalWidth(svg) * zoom}px`
    svg.style.height = 'auto'
  }, [zoom, rendered.svg])
  function fit() {
    const svg = canvasRef.current?.querySelector('svg')
    const room = frameRef.current?.clientWidth
    if (svg && room) setZoom(Math.max(0.3, Math.min(2.5, (room - 24) / naturalWidth(svg))))
  }
  if (rendered.error && rendered.diagram === diagram) return <p className="inline-error">{rendered.error}</p>
  if (rendered.diagram !== diagram || !rendered.svg) return <p className="muted">Drawing the concept map…</p>
  return <div className="map-card">
    <div className="map-tools" role="group" aria-label="Concept map zoom">
      <button type="button" className="map-tool" aria-label="Zoom out" onClick={() => setZoom((z) => Math.max(0.3, +(z - 0.2).toFixed(2)))}>−</button>
      <span className="map-zoom">{Math.round(zoom * 100)}%</span>
      <button type="button" className="map-tool" aria-label="Zoom in" onClick={() => setZoom((z) => Math.min(3, +(z + 0.2).toFixed(2)))}>+</button>
      <button type="button" className="map-tool" onClick={fit}>Fit width</button>
      <button type="button" className="map-tool" onClick={() => setZoom(1)}>Actual size</button>
    </div>
    <div className="map-frame" ref={frameRef} tabIndex={0} aria-label="Concept map, scroll to explore"><div className="map-canvas" ref={canvasRef} dangerouslySetInnerHTML={{ __html: rendered.svg }} /></div>
  </div>
}

function Quiz({ questions }) {
  const [answers, setAnswers] = useState({})
  const [tries, setTries] = useState(0)
  const [best, setBest] = useState(0)
  const [submitted, setSubmitted] = useState(false)
  const score = questions.reduce((n, item, i) => n + (answers[i] === item.answer ? 1 : 0), 0)
  const answered = Object.keys(answers).length

  function check() { setTries((x) => x + 1); setBest((b) => Math.max(b, score)); setSubmitted(true) }
  function retry() { setAnswers({}); setSubmitted(false) }

  return <div className="quiz-list">
    {questions.map((item, i) => <fieldset className="quiz-question" key={`${i}-${item.question}`} disabled={submitted}>
      <legend><span className="question-number">{String(i + 1).padStart(2, '0')}</span><RichText text={item.question} /></legend>
      <div className="quiz-choices">{item.choices.map((choice) => <label className={`quiz-choice ${submitted && choice === item.answer ? 'choice-correct' : submitted && answers[i] === choice ? 'choice-incorrect' : ''}`} key={choice}>
        <input type="radio" name={`quiz-${i}`} checked={answers[i] === choice} onChange={() => setAnswers((prev) => ({ ...prev, [i]: choice }))} /><span><RichText text={choice} /></span>
      </label>)}</div>
      {submitted && <p className={`quiz-feedback ${answers[i] === item.answer ? 'feedback-correct' : 'feedback-incorrect'}`}>
        <strong><RichText text={answers[i] === item.answer ? 'Correct.' : answers[i] ? `Not quite. Correct answer: ${item.answer}` : `Unanswered. Correct answer: ${item.answer}`} /></strong> <RichText text={item.explanation} />
      </p>}
    </fieldset>)}
    <div className="quiz-submit-row">
      {tries > 0 && <strong className="quiz-score">{submitted ? `Score: ${score} / ${questions.length} · ` : ''}Tries: {tries} · Best: {best} / {questions.length}</strong>}
      {!submitted
        ? <button className="primary-button" type="button" disabled={!answered} onClick={check}>Check answers{answered < questions.length ? ` (${answered}/${questions.length} answered)` : ''}</button>
        : <button className="primary-button" type="button" onClick={retry}>Try again</button>}
    </div>
  </div>
}

function Flashcard({ card, index }) {
  const [flipped, setFlipped] = useState(false)
  const flip = () => setFlipped((v) => !v)
  return <div className={`flashcard ${flipped ? 'is-flipped' : ''}`} onClick={() => { if (!window.getSelection()?.toString()) flip() }}>
    <span className="card-kicker">{flipped ? 'ANSWER' : `CARD ${String(index + 1).padStart(2, '0')}`}</span>
    <div className="card-copy" tabIndex={0} aria-label={flipped ? 'Answer, scroll for more' : 'Question, scroll for more'}><RichText text={flipped ? card.answer : card.question} /></div>
    <button type="button" className="card-hint" aria-pressed={flipped} onClick={(e) => { e.stopPropagation(); flip() }}>Tap to {flipped ? 'return to the question' : 'reveal the answer'}</button>
  </div>
}

function AuthPanel({ onAuth }) {
  const [register, setRegister] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError('')
    try { onAuth(await request(`/auth/${register ? 'register' : 'login'}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }) })) }
    catch (err) { setError(err.message) } finally { setBusy(false) }
  }
  return <form className="auth-form" onSubmit={submit}>
    <div className="section-heading"><div><p className="eyebrow">YOUR STUDY LIBRARY</p><h2>{register ? 'Create your account' : 'Sign in to sync your sets'}</h2></div></div>
    <label>Email<input required type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} /></label>
    <label>Password<input required minLength="8" type="password" autoComplete={register ? 'new-password' : 'current-password'} value={password} onChange={(e) => setPassword(e.target.value)} /></label>
    <div className="auth-actions"><button className="primary-button" disabled={busy}>{busy ? 'Please wait…' : register ? 'Create account' : 'Sign in'}</button><button className="text-button" type="button" onClick={() => { setRegister((v) => !v); setError('') }}>{register ? 'I already have an account' : 'Create an account'}</button></div>
    {error && <p className="inline-error" role="alert">{error}</p>}
    <small>Use at least 8 characters. Your saved study sets sync with your account on any device.</small>
  </form>
}

function StudyTabs({ studySet }) {
  const [tab, setTab] = useState('cards')
  const tabs = [['cards', `Flashcards (${studySet.flashcards.length})`], ['quiz', `Quiz (${studySet.quiz.length})`], ['map', 'Concept map']]
  // Every panel stays mounted (just hidden), so quiz answers and flipped cards are kept when switching tabs.
  return <>
    <div className="result-tabs" role="tablist" aria-label="Study material">
      {tabs.map(([id, label]) => <button key={id} type="button" role="tab" id={`tab-${id}`} aria-selected={tab === id} aria-controls={`panel-${id}`} onClick={() => setTab(id)}>{label}</button>)}
    </div>
    <section id="panel-cards" role="tabpanel" aria-labelledby="tab-cards" hidden={tab !== 'cards'}><p className="result-instruction">Select a card to reveal the answer</p><div className="flashcard-grid">{studySet.flashcards.map((card, i) => <Flashcard key={`${studySet.id}-${i}`} card={card} index={i} />)}</div></section>
    <section id="panel-quiz" role="tabpanel" aria-labelledby="tab-quiz" hidden={tab !== 'quiz'}><p className="result-instruction">Retry as often as you like</p><Quiz key={studySet.id} questions={studySet.quiz} /></section>
    <section id="panel-map" role="tabpanel" aria-labelledby="tab-map" hidden={tab !== 'map'}><ConceptMap diagram={studySet.diagram} /></section>
  </>
}

function App() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) || '')
  const [email, setEmail] = useState('')
  const [savedSets, setSavedSets] = useState([])
  const [file, setFile] = useState(null)
  const [autoCards, setAutoCards] = useState(true)
  const [cardCount, setCardCount] = useState(12)
  const [quizCount, setQuizCount] = useState(8)
  const [visual, setVisual] = useState(true)
  const [studySet, setStudySet] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  function signOut() { localStorage.removeItem(TOKEN_KEY); setToken(''); setEmail(''); setSavedSets([]); setStudySet(null); setFile(null) }
  function acceptAuth(data) { localStorage.setItem(TOKEN_KEY, data.token); setToken(data.token); setEmail(data.email); setError('') }

  useEffect(() => {
    if (!token) return
    request('/auth/me', {}, token)
      .then((user) => { setEmail(user.email); return request('/study/sets', {}, token) })
      .then(setSavedSets)
      .catch((err) => { if (err.status === 401) signOut(); else setError(err.message) })
  }, [token])

  function chooseFile(next) {
    setStudySet(null); setError('')
    if (!next) return setFile(null)
    if (!['pdf', 'pptx'].includes(next.name.split('.').pop()?.toLowerCase())) return (setFile(null), setError('Choose a PDF or PowerPoint (.pptx) file.'))
    if (next.size > MAX_FILE_BYTES) return (setFile(null), setError('This file is larger than 20 MB.'))
    setFile(next)
  }

  async function generate(event) {
    event.preventDefault(); if (!file || loading || !token) return
    setLoading(true); setError(''); setStudySet(null)
    const body = new FormData(); body.append('file', file); body.append('card_count', autoCards ? 0 : cardCount); body.append('quiz_count', autoCards ? 0 : quizCount); body.append('visual', visual)
    try { setStudySet(await request('/study/generate', { method: 'POST', body }, token)) }
    catch (err) { if (err.status === 401) signOut(); setError(err.message) } finally { setLoading(false) }
  }
  async function saveSet() {
    try {
      const saved = await request('/study/sets', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(studySet) }, token)
      setStudySet(saved); setSavedSets((items) => [saved, ...items.filter((x) => x.id !== saved.id)])
    } catch (err) { setError(err.message) }
  }
  async function removeSet(id) {
    if (!window.confirm('Remove this saved study set?')) return
    try { await request(`/study/sets/${encodeURIComponent(id)}`, { method: 'DELETE' }, token); setSavedSets((items) => items.filter((x) => x.id !== id)) }
    catch (err) { setError(err.message) }
  }
  function openSet(item) {
    setStudySet(item); setError('')
    setTimeout(() => document.getElementById('results')?.scrollIntoView({ behavior: 'smooth' }), 50)
  }

  const isSaved = studySet && savedSets.some((x) => x.id === studySet.id)
  return <div className="app-shell">
    <header className="topbar"><a className="brand" href="#top"><span className="brand-mark">LY</span><span>Learn It <strong>Your Way</strong></span></a>
      {token ? <div className="account-actions"><span className="account-email">{email}</span><button className="text-button" onClick={signOut}>Sign out</button></div> : <a className="saved-link" href="#account">Sign in</a>}
    </header>
    <main id="top">
      <section className="hero-section"><div className="hero-copy"><p className="eyebrow">YOUR LECTURES, MADE STUDYABLE</p><h1>Learn the material.<br /><span>Your way.</span></h1><p className="hero-description">One upload creates a complete study pack: flashcards, a quiz, and a visual concept map, with math and diagrams included.</p></div><div className="hero-art" aria-hidden="true"><span className="orbit orbit-one" /><span className="orbit orbit-two" /><span className="hero-note note-one">Recall</span><span className="hero-note note-two">Connect</span><span className="hero-note note-three">Practice</span></div></section>
      {!token && <section className="workspace" id="account"><AuthPanel onAuth={acceptAuth} /></section>}
      {token && <section className="workspace"><div className="section-heading"><div><p className="eyebrow">START A STUDY SESSION</p><h2>Build a complete study pack</h2></div><span className="file-limit">PDF or PPTX · up to 20 MB</span></div>
        <form className="upload-form" onSubmit={generate}>
          <label className={`drop-zone ${file ? 'has-file' : ''}`} htmlFor="lecture-file"><input id="lecture-file" type="file" accept=".pdf,.pptx,application/pdf,application/vnd.openxmlformats-officedocument.presentationml.presentation" onChange={(e) => chooseFile(e.target.files?.[0])} /><span className="upload-icon">↑</span><span className="drop-title">{file ? file.name : 'Choose a lecture file'}</span><span className="drop-hint">{file ? `${(file.size / 1048576).toFixed(1)} MB · ready to study` : 'Select a PDF or PowerPoint from your device'}</span><span className="browse-button">Browse files</span></label>
          <div className="generate-controls">
            <div className="count-label">
              <div className="mode-choice" role="radiogroup" aria-label="Number of cards and questions">
                <label className="auto-toggle"><input type="radio" name="count-mode" checked={autoCards} onChange={() => setAutoCards(true)} /> Auto generate</label>
                <label className="auto-toggle"><input type="radio" name="count-mode" checked={!autoCards} onChange={() => setAutoCards(false)} /> Pick the numbers</label>
              </div>
              {!autoCards && <div className="count-row">
                <label>Flashcards<input type="number" inputMode="numeric" min="4" max="50" value={cardCount} onChange={(e) => setCardCount(Math.max(4, Math.min(50, Number(e.target.value) || 4)))} /></label>
                <label>Quiz questions<input type="number" inputMode="numeric" min="3" max="30" value={quizCount} onChange={(e) => setQuizCount(Math.max(3, Math.min(30, Number(e.target.value) || 3)))} /></label>
              </div>}
              <label className="auto-toggle"><input type="checkbox" checked={visual} onChange={(e) => setVisual(e.target.checked)} /> Read equations and diagrams (takes a little longer)</label>
              <small>{autoCards ? 'Longer lectures get more cards and questions.' : 'Cards and questions are spread across the whole lecture.'}</small>
            </div>
            <button className="primary-button generate-button" disabled={!file || loading}>{loading ? <><span className="spinner" />Preparing…</> : 'Create study pack'}</button>
          </div>
        </form>
        {error && <div className="error-banner" role="alert"><span>!</span>{error}</div>}
        {loading && <p className="loading-note" role="status"><strong>Preparing your study materials…</strong> Long lectures may take longer.</p>}
      </section>}

      {studySet && <section className="results-section" id="results"><div className="results-heading"><div><p className="eyebrow">YOUR STUDY MATERIAL{studySet.cached ? ' · REUSED FROM EARLIER' : ''}</p><h2>{studySet.filename}</h2></div><button className="save-button" disabled={isSaved} onClick={saveSet}>{isSaved ? '✓ Saved to account' : '＋ Save to account'}</button></div>
        {studySet.warnings?.length > 0 && <div className="notice" role="status">{studySet.warnings.join(' ')}</div>}
        <StudyTabs key={studySet.id} studySet={studySet} />
      </section>}

      {token && <section className="saved-section" id="saved-sets"><div className="section-heading"><div><p className="eyebrow">AVAILABLE ON YOUR DEVICES</p><h2>Saved study sets</h2></div><span className="file-limit">Synced to your account</span></div>
        {savedSets.length ? <ul className="saved-list">{savedSets.map((item) => <li className="saved-item" key={item.id}><button className="saved-item-main" onClick={() => openSet(item)}><span className="saved-item-icon">▤</span><span className="saved-item-copy"><strong>{item.filename}</strong><small>{new Date(item.createdAt.replace(' ', 'T') + 'Z').toLocaleDateString()}</small></span></button><button className="delete-saved" onClick={() => removeSet(item.id)}>Remove</button></li>)}</ul> : <div className="empty-saved"><span className="empty-icon">▧</span><p>No saved sets yet</p><span>Save a study pack and open it from any device.</span></div>}
      </section>}
    </main><footer className="footer"><span>Learn It Your Way</span><span>Study at your pace, in your format.</span></footer>
  </div>
}

export default App
