import { useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, ArrowDown, ArrowUpRight, Check, ChevronDown, CircleHelp, FileImage, FlaskConical, Leaf, LoaderCircle, Plus, RotateCcw, ScanLine, ShieldCheck, Sparkles, Upload, X } from 'lucide-react';
import { analyzeImage, getClientId, getHistory, getWatchlist, reviewText, saveWatchlist } from './services/api';
import './App.css';

const ACCEPTED = ['image/jpeg', 'image/png', 'image/webp'];
const STORE = 'inci-sight-watchlist';
const HISTORY = 'inci-sight-local-history';
const loadLocal = (key, fallback) => { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; } };

function Brand() {
  return <a className="brand" href="#top" aria-label="INCI Sight home"><span className="brand-mark"><Leaf size={17} /><ScanLine size={12} /></span><span>inci<span className="brand-light">sight</span></span></a>;
}

function Header({ section, setSection }) {
  return <header className="topbar"><Brand /><nav aria-label="Main navigation"><button className={section === 'scan' ? 'nav-link active' : 'nav-link'} onClick={() => { setSection('scan'); document.querySelector('#scanner')?.scrollIntoView({ behavior: 'smooth' }); }}>Scan a label</button><button className={section === 'watchlist' ? 'nav-link active' : 'nav-link'} onClick={() => { setSection('watchlist'); document.querySelector('#watchlist')?.scrollIntoView({ behavior: 'smooth' }); }}>My watchlist</button><a className="top-cta" href="#scanner">Start a scan <ArrowUpRight size={15} /></a></nav></header>;
}

function Watchlist({ items, onAdd, onRemove, persistence }) {
  const [value, setValue] = useState('');
  const [error, setError] = useState('');
  const submit = (event) => {
    event.preventDefault();
    const name = value.trim().replace(/\s+/g, ' ');
    if (name.length < 3) return setError('Enter at least 3 characters.');
    if (items.some((item) => item.toLowerCase() === name.toLowerCase())) return setError('That ingredient is already on your list.');
    onAdd(name); setValue(''); setError('');
  };
  return <section className="watchlist-panel paper-card" id="watchlist">
    <div className="panel-eyebrow"><span className="eyebrow-icon"><ShieldCheck size={15} /></span> YOUR PERSONAL LIST</div>
    <h2>Ingredients to look out for.</h2>
    <p className="muted">Add an ingredient name. We’ll check each scan for exact names and a few known label aliases, like fragrance / parfum.</p>
    <form className="watch-form" onSubmit={submit}><label className="sr-only" htmlFor="watch-entry">Ingredient to watch</label><input id="watch-entry" value={value} onChange={(e) => setValue(e.target.value)} placeholder="e.g. Parfum, lanolin, methylparaben" maxLength={128} /><button className="button forest small" type="submit"><Plus size={16} /> Add</button></form>
    {error && <p className="inline-error" role="alert">{error}</p>}
    <div className="watch-chips">{items.length ? items.map((name) => <span className="watch-chip" key={name}>{name}<button type="button" aria-label={`Remove ${name}`} onClick={() => onRemove(name)}><X size={13} /></button></span>) : <p className="empty-note">Your list is empty. Add an ingredient you want to check for.</p>}</div>
    <div className="persistence-note"><span className={persistence ? 'pulse-dot ready' : 'pulse-dot'} />{persistence ? 'Saved to this browser workspace' : 'Saved in this browser only'}<span className="help-tip" title="This workspace uses a browser ID, not a secure sign-in account."><CircleHelp size={14} /></span></div>
  </section>;
}

function UploadPanel({ onAnalyze, busy, setResult, setBusy }) {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState('');
  const [productName, setProductName] = useState('');
  const [error, setError] = useState('');
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);
  const abortRef = useRef(null);
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);
  const choose = (next) => {
    if (!next) return;
    if (!ACCEPTED.includes(next.type)) { setError('Use a JPG, PNG, or WEBP image.'); return; }
    if (next.size > 10 * 1024 * 1024) { setError('This image is over the 10 MB limit. Choose a smaller photo.'); return; }
    if (preview) URL.revokeObjectURL(preview);
    setFile(next); setPreview(URL.createObjectURL(next)); setError(''); setResult(null);
  };
  const clear = () => { if (preview) URL.revokeObjectURL(preview); setFile(null); setPreview(''); setError(''); if (inputRef.current) inputRef.current.value = ''; };
  const sample = async () => {
    try {
      const response = await fetch('/sample-label.png');
      if (!response.ok) throw new Error('The sample label is unavailable.');
      const blob = await response.blob();
      choose(new File([blob], 'sample-label.png', { type: 'image/png' }));
      setProductName('Provided sample label');
    } catch (e) { setError(e.message); }
  };
  const run = async () => {
    if (!file) return setError('Add a photo of the ingredients panel before scanning.');
    setError(''); setBusy(true); abortRef.current = new AbortController();
    try { await onAnalyze(file, productName, abortRef.current.signal); }
    catch (e) { if (e.name !== 'AbortError') setError(e.message); }
    finally { setBusy(false); }
  };
  return <section className="upload-panel paper-card" id="scanner">
    <div className="panel-eyebrow"><span className="eyebrow-icon"><ScanLine size={15} /></span> LABEL READER <span className="model-tag"><Sparkles size={12} /> OCR + ingredient parsing</span></div>
    <h2>Let’s read the small print.</h2>
    <p className="muted">Photograph the ingredient panel as straight-on and in focus as you can. Your image is processed for this scan, not saved to history.</p>
    <div className={`dropzone ${dragging ? 'dragging' : ''} ${preview ? 'has-image' : ''}`} onDragOver={(e) => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={(e) => { e.preventDefault(); setDragging(false); choose(e.dataTransfer.files[0]); }}>
      {preview ? <><img className="image-preview" src={preview} alt="Preview of the cosmetic ingredient label" />{busy && <div className="scan-sweep" />}{!busy && <button className="remove-image" aria-label="Remove selected image" onClick={clear}><X size={16} /></button>}</> : <div className="drop-content"><span className="upload-icon"><FileImage size={23} /></span><strong>Drop your label photo here</strong><span className="muted tiny">or browse your device · JPG, PNG, WEBP · up to 10 MB</span><button className="button outline small" type="button" onClick={() => inputRef.current?.click()}><Upload size={15} /> Choose an image</button></div>}
      <input ref={inputRef} className="sr-only" type="file" accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp" aria-label="Choose ingredient label image" onChange={(e) => choose(e.target.files?.[0])} />
    </div>
    <div className="upload-meta"><button type="button" className="text-button" onClick={sample}>Try the provided sample label <ArrowUpRight size={13} /></button><span>Clear, close-up photos work best</span></div>
    <div className="product-field"><label htmlFor="product-name">Product name <span>optional</span></label><input id="product-name" value={productName} onChange={(e) => setProductName(e.target.value)} placeholder="e.g. Daily face cream" maxLength={255} /></div>
    {error && <div className="error-banner" role="alert"><AlertCircle size={17} /> {error}</div>}
    <div className="scan-actions">{busy ? <><span className="working"><LoaderCircle size={17} className="spin" /> Reading the label — first scan may take longer while the OCR model loads.</span><button className="button outline small" onClick={() => { abortRef.current?.abort(); setBusy(false); }}>Cancel</button></> : <button className="button forest scan-button" onClick={run} disabled={!file}><ScanLine size={17} /> Scan ingredients <ArrowUpRight size={16} /></button>}</div>
  </section>;
}

function Results({ result, watchlist, onReview, onNewScan }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(result?.extracted_text || '');
  const [reviewBusy, setReviewBusy] = useState(false);
  const [reviewError, setReviewError] = useState('');
  useEffect(() => { setText(result?.extracted_text || ''); setEditing(false); setReviewError(''); }, [result]);
  const matchByIngredient = useMemo(() => {
    const mapping = new Map();
    (result?.matches || []).forEach((match) => {
      const key = (match.detected_ingredient || match.matched_term || '').toLowerCase();
      mapping.set(key, [...(mapping.get(key) || []), match]);
    });
    return mapping;
  }, [result]);
  const matchesFor = (ingredient) => {
    const exact = matchByIngredient.get(ingredient.toLowerCase());
    if (exact) return exact;
    return (result?.matches || []).filter((item) => item.detected_ingredient?.toLowerCase() === ingredient.toLowerCase());
  };
  const rerun = async () => {
    setReviewBusy(true); setReviewError('');
    try { await onReview(text); setEditing(false); }
    catch (e) { setReviewError(e.message); }
    finally { setReviewBusy(false); }
  };
  return <section className="results-panel paper-card" id="results" aria-live="polite">
    <div className="results-top"><div><div className="panel-eyebrow"><span className="eyebrow-icon"><FlaskConical size={15} /></span> YOUR LABEL NOTES</div><h2>{result.product_name || 'Scan results'}</h2><p className="muted">{result.ingredients.length} ingredient{result.ingredients.length === 1 ? '' : 's'} parsed from this label</p></div><button className="button outline small" onClick={onNewScan}><RotateCcw size={15} /> New scan</button></div>
    {(result.matches || []).length ? <div className="match-alert"><span className="alert-mark"><AlertCircle size={19} /></span><div><strong>{result.matches.length} watchlist match{result.matches.length === 1 ? '' : 'es'} found</strong><p>{result.matches.map((match) => `${match.detected_ingredient || match.matched_term} (${match.ingredient})`).join(' · ')}</p><small>These match your personal list. A match is not a medical assessment.</small></div></div> : watchlist.length ? <div className="clear-alert"><Check size={17} /><span>No names from your watchlist were found in the parsed ingredients.</span></div> : <div className="neutral-alert"><ShieldCheck size={17} /><span>Add ingredients to your watchlist to check them during a scan.</span></div>}
    {result.uncertain_text?.length > 0 && <div className="uncertain-alert"><CircleHelp size={16} /><span>{result.uncertain_text.length} OCR line{result.uncertain_text.length === 1 ? '' : 's'} had low recognition confidence. Review the text below before relying on the parsed list.</span></div>}
    {!result.ingredients.length && <div className="uncertain-alert"><AlertCircle size={16} /><span>No ingredient candidates could be parsed. Try a closer photo or edit the recognized text below.</span></div>}
    <div className="ingredient-heading"><div><span className="section-kicker">DETECTED INCI</span><h3>Ingredient list <span className="count-pill">{result.ingredients.length}</span></h3></div><span className="sequence-note">Listed in label order</span></div>
    <ol className="ingredient-list">{result.ingredients.map((ingredient, index) => {
      const matches = matchesFor(ingredient);
      return <li className={matches.length ? 'ingredient-row flagged' : 'ingredient-row'} key={`${ingredient}-${index}`}><span className="ingredient-index">{String(index + 1).padStart(2, '0')}</span><span className="ingredient-name">{ingredient}</span>{matches.length > 0 && <span className="flag-label"><AlertCircle size={12} /> Watchlist</span>}</li>;
    })}</ol>
    <div className="ocr-review"><div className="review-heading"><div><span className="section-kicker">SOURCE TEXT</span><h3>Check what the camera read</h3></div><button className="text-button" onClick={() => setEditing(!editing)}>{editing ? 'Close editor' : 'Edit text'} <ChevronDown size={14} className={editing ? 'rotate' : ''} /></button></div>
      {editing ? <><textarea value={text} onChange={(e) => setText(e.target.value)} rows={5} aria-label="Corrected OCR label text" /><div className="review-actions"><span className="tiny muted">Correct the text, then rebuild the ingredient list.</span><button className="button forest small" disabled={reviewBusy} onClick={rerun}>{reviewBusy ? <LoaderCircle className="spin" size={15} /> : <Check size={15} />} Re-parse text</button></div>{reviewError && <p className="inline-error" role="alert">{reviewError}</p>}</> : <p className="recognized-text">{result.extracted_text || 'No readable text was returned by OCR.'}</p>}
    </div>
    <p className="disclaimer"><CircleHelp size={14} /> OCR can misread small, curved, reflective, or blurry print. Verify the original package; absence of a match does not guarantee safety.</p>
  </section>;
}

function RecentScans({ items, onSelect }) {
  return <section className="recent-panel paper-card"><div className="recent-title"><div><span className="section-kicker">YOUR WORKSPACE</span><h3>Recent scans</h3></div><span className="recent-count">{items.length}</span></div>{items.length ? <div className="recent-list">{items.slice(0, 4).map((scan) => <button className="recent-item" key={scan.id || `${scan.product_name}-${scan.created_at}`} onClick={() => onSelect(scan)}><span className="recent-leaf"><Leaf size={15} /></span><span className="recent-info"><strong>{scan.product_name || 'Unnamed product'}</strong><small>{scan.ingredients?.length || 0} ingredients · {scan.matches?.length || 0} matches</small></span><ArrowUpRight size={14} /></button>)}</div> : <div className="recent-empty"><span className="recent-leaf"><ArrowDown size={15} /></span><p>Your scans will appear here. Label images are not stored.</p></div>}<p className="storage-caption">History stores label text and ingredient names only.</p></section>;
}

export default function App() {
  const clientId = useMemo(() => getClientId(), []);
  const [watchlist, setWatchlist] = useState(() => loadLocal(STORE, []));
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState(() => loadLocal(HISTORY, []));
  const [busy, setBusy] = useState(false);
  const [section, setSection] = useState('scan');
  const [persistent, setPersistent] = useState(false);
  const [status, setStatus] = useState('Loading your browser workspace');
  useEffect(() => {
    let active = true;
    Promise.all([getWatchlist(clientId), getHistory(clientId)]).then(([w, h]) => {
      if (!active) return;
      setPersistent(Boolean(w.persistent || h.persistent));
      if (w.persistent && Array.isArray(w.ingredients)) {
        if (w.ingredients.length === 0 && watchlist.length > 0) saveWatchlist(watchlist, clientId).catch(() => {});
        else setWatchlist(w.ingredients);
      }
      if (h.persistent && Array.isArray(h.scans)) setHistory(h.scans);
      setStatus('Workspace ready');
    }).catch(() => setStatus('Using browser-local workspace'));
    return () => { active = false; };
  }, [clientId]);
  useEffect(() => { try { localStorage.setItem(STORE, JSON.stringify(watchlist)); } catch { /* storage may be unavailable */ } }, [watchlist]);
  useEffect(() => { try { localStorage.setItem(HISTORY, JSON.stringify(history)); } catch { /* storage may be unavailable */ } }, [history]);
  const updateWatchlist = (next) => {
    setWatchlist(next);
    saveWatchlist(next, clientId).then((data) => setPersistent(Boolean(data.persistent))).catch(() => setPersistent(false));
  };
  const runAnalysis = async (file, productName, signal) => {
    const data = await analyzeImage(file, watchlist, clientId, signal, productName);
    const next = { ...data, product_name: productName || '', image_name: file.name };
    setResult(next);
    if (data.scan_id) {
      getHistory(clientId).then((h) => { if (h.persistent) { setPersistent(true); setHistory(h.scans || []); } });
    } else {
      setHistory((items) => [{ id: `${Date.now()}`, product_name: next.product_name, ingredients: data.ingredients, matches: data.matches, created_at: new Date().toISOString(), extracted_text: data.extracted_text }, ...items].slice(0, 10));
    }
    document.querySelector('#results')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };
  const runReview = async (text) => {
    const data = await reviewText(text, watchlist, clientId, result.scan_id, result.product_name);
    setResult((current) => ({ ...current, ...data, product_name: current.product_name, image_name: current.image_name }));
  };
  const selectRecent = (scan) => {
    setResult({ ...scan, extracted_text: scan.extracted_text || '', image_name: scan.filename || '', product_name: scan.product_name || '', uncertain_text: [], detections: [], scan_id: scan.id });
    document.querySelector('#results')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };
  return <div id="top" className="app-shell">
    <Header section={section} setSection={setSection} />
    <main>
      <section className="hero"><div className="hero-copy"><span className="hero-kicker"><span className="hero-dot" /> INGREDIENTS, IN PLAIN SIGHT</span><h1>Read the small print<br /><em>with a little more confidence.</em></h1><p>Scan a cosmetic label, get an ingredient list you can check, and keep your own watchlist close at hand.</p><div className="hero-actions"><a className="button forest" href="#scanner"><ScanLine size={16} /> Scan a label <ArrowUpRight size={15} /></a><a className="quiet-link" href="#watchlist">Set up your watchlist <ArrowDown size={14} /></a></div><div className="trust-strip"><span><Check size={14} /> OCR-powered label reading</span><span><Check size={14} /> Personal ingredient checks</span><span><Check size={14} /> Correctable results</span></div></div><div className="hero-art" aria-hidden="true"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="hero-leaf"><Leaf size={101} strokeWidth={0.9}/></div><div className="note-card"><span className="note-top"><span>FIELD NOTE 01</span><ScanLine size={14}/></span><span className="note-rule"/><span className="note-label">Aqua · Glycerin</span><span className="note-label">Niacinamide · Panthenol</span><span className="note-match"><span/> on your list</span></div><span className="stamp">READ<br/>WITH CARE</span></div></section>
      <div className="workspace-grid"><div className="workspace-main"><UploadPanel onAnalyze={runAnalysis} busy={busy} setResult={setResult} setBusy={setBusy}/>{result && <Results result={result} watchlist={watchlist} onReview={runReview} onNewScan={() => { setResult(null); document.querySelector('#scanner')?.scrollIntoView({ behavior: 'smooth' }); }}/>}</div><aside className="workspace-rail"><Watchlist items={watchlist} onAdd={(name) => updateWatchlist([...watchlist, name])} onRemove={(name) => updateWatchlist(watchlist.filter((item) => item !== name))} persistence={persistent}/><RecentScans items={history} onSelect={selectRecent}/><div className="privacy-note"><ShieldCheck size={17}/><span><strong>Not medical advice</strong><br/>A reading aid, not a diagnosis. Double-check packaging if you have a known allergy.</span></div></aside></div>
    </main>
    <footer><Brand/><span>Careful reading. Clearer choices.</span><span className="footer-status"><span className="pulse-dot ready"/> {status}</span></footer>
  </div>;
}
