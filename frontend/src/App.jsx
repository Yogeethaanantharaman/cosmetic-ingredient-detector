import { useEffect, useMemo, useRef, useState } from 'react'
import { Leaf, ScanLine, Upload, X, Search, ChevronDown, Menu, AlertCircle, Sparkles } from 'lucide-react'
import { analyzeImage, demoResult, CATS } from './services/api'
import './App.css'

const OK_TYPES = ['image/jpeg', 'image/png', 'image/webp']
const STATUS = ['Scanning ingredient label...', 'Extracting printed text...', 'Identifying cosmetic ingredients...', 'Preparing your ingredient breakdown...']
const GUIDE = [
  ['Niacinamide', 'Active', 'A vitamin B3 derivative used to support the skin barrier and even tone.'],
  ['Hyaluronic Acid', 'Humectant', 'Binds water on the skin surface for a plumper, hydrated feel.'],
  ['Glycerin', 'Humectant', 'A classic moisturizer that draws water into the outer skin layer.'],
  ['Ceramides', 'Emollient', 'Skin-identical lipids that help reinforce the moisture barrier.'],
  ['Salicylic Acid', 'Active', 'A BHA that exfoliates inside pores; can be drying for some.'],
  ['Retinol', 'Active', 'A vitamin A derivative for texture and fine lines; may cause irritation at first.'],
  ['Panthenol', 'Active', 'Provitamin B5 that soothes and helps skin retain moisture.'],
  ['Fragrance', 'Fragrance', 'A scent blend; a common source of sensitivity for reactive skin.'],
]

const go = (id) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })

function useStored(key, init) {
  const [v, setV] = useState(() => {
    try { return JSON.parse(localStorage.getItem(key)) ?? init } catch { return init }
  })
  useEffect(() => { try { localStorage.setItem(key, JSON.stringify(v)) } catch { /* ignore */ } }, [key, v])
  return [v, setV]
}
const hit = (ing, list) => list.some((a) => ing.name.toLowerCase().includes(a.toLowerCase()))

function Allergies({ allergies, setAllergies, saved, setSaved }) {
  const [v, setV] = useState('')
  const [msg, setMsg] = useState('')
  const add = (e) => {
    e.preventDefault()
    const t = v.trim()
    if (t.length < 3) return setMsg('Enter at least 3 characters.')
    if (allergies.some((a) => a.toLowerCase() === t.toLowerCase())) return setMsg('Already in your list.')
    setAllergies([...allergies, t]); setV(''); setMsg('')
  }
  return (
    <section id="allergies" className="section">
      <h2>My Allergies</h2>
      <p className="lead">Add ingredients you react to. We'll flag them in every product you scan. Add alternate names too (for example, both Fragrance and Parfum).</p>
      <div className="glass allergy-box">
        <form className="row" onSubmit={add}>
          <input aria-label="Allergen name" placeholder="e.g. Parfum, Lanolin, Phenoxyethanol" value={v} onChange={(e) => setV(e.target.value)} />
          <button className="btn primary" type="submit">Add</button>
        </form>
        {msg && <p className="empty" role="alert">{msg}</p>}
        <div className="chips">
          {allergies.length === 0 && <p className="empty">No allergens saved yet.</p>}
          {allergies.map((a) => (
            <span key={a} className="chip big">{a}
              <button aria-label={`Remove ${a}`} onClick={() => setAllergies(allergies.filter((x) => x !== a))}><X size={12} /></button>
            </span>
          ))}
        </div>
        <h3>Products I'm allergic to</h3>
        {saved.length === 0 && <p className="empty">Scan a product and save it here when it contains one of your allergens.</p>}
        <ul className="saved">
          {saved.map((p, i) => (
            <li key={i}>
              <div><b>{p.name}</b><small> · {p.date}</small><br /><small>Contains: {p.ingredients.join(', ')}</small></div>
              <button className="icon-btn" aria-label={`Delete ${p.name}`} onClick={() => setSaved(saved.filter((_, j) => j !== i))}><X size={16} /></button>
            </li>
          ))}
        </ul>
        <small>Matching is by ingredient name only. It's an aid, not medical advice. Always check the label and ask a professional if unsure.</small>
      </div>
    </section>
  )
}

function Logo() {
  return <span className="logo"><span className="logo-mark"><Leaf size={18} /><ScanLine size={12} /></span>INCI Sight</span>
}

function Navbar() {
  const [open, setOpen] = useState(false)
 const links = [['Home', 'home'], ['Analyze Ingredients', 'analyze'], ['My Allergies', 'allergies'], ['How It Works', 'how'], ['Ingredient Guide', 'guide']]
  const nav = (id) => { setOpen(false); go(id) }
  return (
    <header className="nav">
      <Logo />
      <button className="icon-btn menu" aria-label="Toggle menu" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? <X /> : <Menu />}</button>
      <nav className={open ? 'open' : ''} aria-label="Main">
        {links.map(([l, id]) => <button key={id} className="link" onClick={() => nav(id)}>{l}</button>)}
        <button className="btn primary" onClick={() => nav('analyze')}>Analyze My Product</button>
      </nav>
    </header>
  )
}

function Hero() {
  return (
    <section id="home" className="hero">
      <div>
        <span className="badge">AI-POWERED SKINCARE INTELLIGENCE</span>
        <h1>Know What Goes Into Your Skin.</h1>
        <p>Scan the ingredient label on the back of any cosmetic product and understand what's inside, in plain language.</p>
        <div className="row">
          <button className="btn primary" onClick={() => go('analyze')}>Analyze My Product</button>
          <button className="btn ghost" onClick={() => go('guide')}>Explore Ingredients</button>
        </div>
        <ul className="trust"><li>Ingredient Label OCR</li><li>Ingredient Breakdown</li><li>Easy-to-Understand Results</li></ul>
      </div>
      <div className="visual" aria-hidden="true">
        <div className="blob" />
        <div className="bottle b1"><i /></div><div className="bottle b2"><i /></div><div className="jar" />
        <Leaf className="leaf l1" size={90} /><Leaf className="leaf l2" size={60} />
        <span className="tag t1">Niacinamide</span><span className="tag t2">Hyaluronic Acid</span><span className="tag t3">Ceramides</span>
        <div className="float-card glass"><ScanLine size={16} /> 12 ingredients decoded<div className="bar"><b /></div></div>
      </div>
    </section>
  )
}

function Analyzer({ onResult }) {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [name, setName] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [demo, setDemo] = useState(false)
  const [msg, setMsg] = useState(0)
  const [drag, setDrag] = useState(false)
  const ctl = useRef(null)
  const input = useRef(null)

  useEffect(() => {
    if (!busy) return
    const t = setInterval(() => setMsg((m) => (m + 1) % STATUS.length), 1400)
    return () => clearInterval(t)
  }, [busy])
  useEffect(() => () => preview && URL.revokeObjectURL(preview), [preview])

  const pick = (f) => {
    if (!f) return
    if (!OK_TYPES.includes(f.type)) return setErr('Please upload a JPG, JPEG, PNG, or WEBP image.')
    if (f.size > 10 * 1024 * 1024) return setErr('That image is over 10 MB. Please choose a smaller one.')
    setErr(''); setFile(f); setPreview(URL.createObjectURL(f))
  }
  const clear = () => { setFile(null); setPreview(null); setErr(''); if (input.current) input.current.value = '' }
  const cancel = () => { ctl.current?.abort(); setBusy(false) }

  const run = async () => {
    if (!file) return setErr('Please upload a photo of the ingredient label first.')
    setErr(''); setBusy(true); setMsg(0)
    ctl.current = new AbortController()
    try {
      const r = demo ? (await new Promise((res) => setTimeout(res, 3200)), demoResult()) : await analyzeImage(file, ctl.current.signal)
      if (!r.ingredients.length) throw new Error('No ingredients were detected. Try a sharper, closer photo of the label.')
      onResult({ ...r, image: preview, productName: name })
    } catch (e) {
      if (e.name !== 'AbortError') setErr(e.message)
    } finally { setBusy(false) }
  }

  return (
    <section id="analyze" className="section">
      <h2>Let's Decode Your Skincare.</h2>
      <p className="lead">Upload a clear photo of the ingredient list on the back of your cosmetic product.</p>
      <div className="upload glass">
        <div
          className={`drop ${drag ? 'drag' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files[0]) }}
        >
          {preview ? (
            <div className="preview">
              <img src={preview} alt="Uploaded ingredient label preview" />
              {busy && <div className="scan" />}
              {!busy && <button className="icon-btn rm" aria-label="Remove image" onClick={clear}><X size={16} /></button>}
            </div>
          ) : (
            <>
              <Upload size={32} />
              <p><strong>Drag and drop</strong> your label photo here</p>
              <small>JPG, JPEG, PNG or WEBP, up to 10 MB</small>
              <button className="btn ghost" onClick={() => input.current?.click()}>Browse files</button>
            </>
          )}
          <input ref={input} type="file" hidden accept=".jpg,.jpeg,.png,.webp" aria-label="Upload ingredient label image" onChange={(e) => pick(e.target.files[0])} />
        </div>
        <div className="form">
          <div className="example" aria-label="Example of an ingredient label">
            <small>Photograph this part:</small>
            <p>BACK LABEL<br /><mark>INGREDIENTS: Aqua, Glycerin, Niacinamide, Panthenol...</mark><br />Directions: apply daily</p>
          </div>
          <label htmlFor="pname">Product name (optional)</label>
          <input id="pname" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Daily Barrier Cream" />
          <label className="check"><input type="checkbox" checked={demo} onChange={(e) => setDemo(e.target.checked)} /> Demo mode (sample results, no backend)</label>
          {err && <div className="alert" role="alert"><AlertCircle size={16} /> {err}</div>}
          {busy ? (
            <div className="row"><span className="status" aria-live="polite">{STATUS[msg]}</span><button className="btn ghost" onClick={cancel}>Cancel</button></div>
          ) : (
            <button className="btn primary" onClick={run}>Analyze Ingredients</button>
          )}
        </div>
      </div>
    </section>
  )
}

function Donut({ items }) {
  const counts = CATS.map((c) => [c, items.filter((i) => i.category === c).length]).filter(([, n]) => n)
  const total = counts.reduce((s, [, n]) => s + n, 0)
  if (!total) return <p className="empty">Category data wasn't returned for this analysis.</p>
  const colors = ['#8da07a', '#d9b99b', '#6f7d56', '#c9a38f', '#e8c4c0', '#1f3a2e', '#b9b39f']
  let acc = 0
  const stops = counts.map(([c, n]) => { const s = acc; acc += (n / total) * 100; return `${colors[CATS.indexOf(c)]} ${s}% ${acc}%` })
  return (
    <div className="donut-wrap">
      <div className="donut" style={{ background: `conic-gradient(${stops.join(',')})` }}><span>{total}<small>categorized</small></span></div>
      <ul>{counts.map(([c, n]) => <li key={c}><i style={{ background: colors[CATS.indexOf(c)] }} />{c} <b>{n}</b></li>)}</ul>
    </div>
  )
}

function Results({ r, onReset, allergies, onSave }) {
  const [q, setQ] = useState('')
  const [cat, setCat] = useState('All')
  const [concern, setConcern] = useState(false)
  const [mine, setMine] = useState(false)
  const [open, setOpen] = useState(null)
  const [all, setAll] = useState(false)
  const [savedNow, setSavedNow] = useState(false)
  const flagged = useMemo(() => r.ingredients.filter((i) => hit(i, allergies)), [r, allergies])
  const shown = useMemo(() => r.ingredients.filter((i) =>
    i.name.toLowerCase().includes(q.toLowerCase()) &&
    (cat === 'All' || i.category === cat) &&
    (!concern || i.concerns.length) &&
    (!mine || hit(i, allergies))), [r, q, cat, concern, mine, allergies])
  const list = all ? shown : shown.slice(0, 6)
  return (
    <section id="results" className="section">
      {r.demo && <div className="demo-banner">DEMO MODE: sample data, not analysis of your image.</div>}
      {flagged.length > 0 && (
        <div className="allergy-alert" role="alert">
          <AlertCircle size={18} />
          <div>
            <b>{flagged.length} ingredient{flagged.length > 1 ? 's' : ''} match your allergy list:</b> {flagged.map((f) => f.name).join(', ')}
            <div><button className="btn ghost" disabled={savedNow} onClick={() => { onSave(r, flagged); setSavedNow(true) }}>
              {savedNow ? 'Saved to my allergic products' : 'Save this product as allergic'}</button></div>
          </div>
        </div>
      )}
      {allergies.length > 0 && flagged.length === 0 && <div className="ok-banner">No ingredients match your allergy list.</div>}
      <div className="res-head glass">
        {r.image && <img src={r.image} alt="Analyzed label" />}
        <div>
          <h2>{r.productName || 'Your product'}</h2>
          <p><b>{r.ingredients.length}</b> ingredients detected</p>
          {r.text && <details><summary>Extracted label text</summary><p className="raw">{r.text}</p></details>}
        </div>
        <button className="btn ghost" onClick={onReset}>Analyze Another Product</button>
      </div>
      <div className="glass overview"><h3>Ingredient overview</h3><Donut items={r.ingredients} /></div>
      <div className="filters">
        <div className="search"><Search size={16} /><input aria-label="Search ingredients" placeholder="Search ingredients" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <select aria-label="Filter by category" value={cat} onChange={(e) => setCat(e.target.value)}><option>All</option>{CATS.map((c) => <option key={c}>{c}</option>)}</select>
        <label className="check"><input type="checkbox" checked={concern} onChange={(e) => setConcern(e.target.checked)} /> Has possible sensitivities</label>
        <label className="check"><input type="checkbox" checked={mine} onChange={(e) => setMine(e.target.checked)} /> Matches my allergies</label>
      </div>
      {!shown.length && <p className="empty">No ingredients match your filters.</p>}
      <div className="cards">
        {list.map((i, n) => (
          <article key={i.name + n} className={`card glass ${hit(i, allergies) ? 'flag' : ''}`}>
            <button aria-expanded={open === n} onClick={() => setOpen(open === n ? null : n)}>
              <span><b>{i.name}</b>{i.category && <em className="chip">{i.category}</em>}{hit(i, allergies) && <em className="chip warn">Your allergy</em>}</span>
              <ChevronDown size={16} className={open === n ? 'rot' : ''} />
            </button>
            {i.function && <small>{i.function}</small>}
            {open === n && (
              <div className="detail">
                <p>{i.explanation || 'No description available for this ingredient.'}</p>
                {!!i.benefits.length && <p><b>Potential benefits:</b> {i.benefits.join(', ')}</p>}
                {!!i.concerns.length && <p><b>Possible sensitivity (not a general hazard):</b> {i.concerns.join(', ')}</p>}
                <small>Source: {i.source || 'Not provided'}</small>
              </div>
            )}
          </article>
        ))}
      </div>
      {shown.length > 6 && <button className="btn ghost center" onClick={() => setAll(!all)}>{all ? 'Show fewer' : 'View All Ingredients'}</button>}
    </section>
  )
}

function How() {
  const s = [[Upload, 'Upload', 'Take a clear photo of the ingredient label.'], [ScanLine, 'Decode', 'OCR extracts the printed ingredient text.'], [Sparkles, 'Understand', 'Explore functions, benefits, and potential concerns.']]
  return (
    <section id="how" className="section">
      <h2>How It Works</h2>
      <div className="steps">{s.map(([Ic, t, d], i) => <div key={t} className="step glass"><span className="num">{i + 1}</span><Ic size={26} /><h3>{t}</h3><p>{d}</p></div>)}</div>
    </section>
  )
}

function Guide() {
  const [q, setQ] = useState('')
  const [cat, setCat] = useState('All')
  const f = GUIDE.filter(([n, c]) => n.toLowerCase().includes(q.toLowerCase()) && (cat === 'All' || c === cat))
  return (
    <section id="guide" className="section">
      <h2>Ingredient Guide</h2>
      <p className="lead">Educational examples only. These are not results from your uploaded product.</p>
      <div className="filters">
        <div className="search"><Search size={16} /><input aria-label="Search guide" placeholder="Search guide" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <select aria-label="Guide category" value={cat} onChange={(e) => setCat(e.target.value)}><option>All</option>{[...new Set(GUIDE.map((g) => g[1]))].map((c) => <option key={c}>{c}</option>)}</select>
      </div>
      <div className="cards">{f.map(([n, c, d]) => <article key={n} className="card glass"><b>{n}</b><em className="chip">{c}</em><p>{d}</p></article>)}</div>
      {!f.length && <p className="empty">No matching ingredients.</p>}
    </section>
  )
}

export default function App() {
  const [result, setResult] = useState(null)
  const [allergies, setAllergies] = useStored('inci-allergies', [])
  const [saved, setSaved] = useStored('inci-allergic-products', [])
  useEffect(() => { if (result) setTimeout(() => go('results'), 100) }, [result])
  const saveProduct = (r, flagged) =>
    setSaved([...saved, { name: r.productName || 'Unnamed product', ingredients: flagged.map((f) => f.name), date: new Date().toLocaleDateString() }])
  return (
    <>
      <Navbar />
      <main>
        <Hero />
        {result ? <Results r={result} allergies={allergies} onSave={saveProduct} onReset={() => { setResult(null); go('analyze') }} /> : null}
        <Analyzer onResult={setResult} />
        <Allergies allergies={allergies} setAllergies={setAllergies} saved={saved} setSaved={setSaved} />
        <How />
        <Guide />
      </main>
      <footer className="footer">
        <Logo />
        <p>INCI Sight decodes cosmetic ingredient labels into plain-language information.</p>
        <p><button className="link" onClick={() => go('home')}>Home</button><button className="link" onClick={() => go('analyze')}>Analyze</button><button className="link" onClick={() => go('allergies')}>My Allergies</button><button className="link" onClick={() => go('how')}>How It Works</button><button className="link" onClick={() => go('guide')}>Ingredient Guide</button></p>
        <small>Privacy: your allergy list and saved products are stored only in this browser. Uploaded images are handled according to this application's actual backend storage policy. Educational information only; it does not replace professional medical advice.</small>
      </footer>
    </>
  )
}