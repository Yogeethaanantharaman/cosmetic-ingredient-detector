// Backend contract is ASSUMED: POST {API_URL}/analyze, multipart field "file".
// Verify against your backend and adjust ENDPOINT / FIELD below.
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const ENDPOINT = '/analyze'
const FIELD = 'file'

const CATS = ['Humectant', 'Emollient', 'Surfactant', 'Preservative', 'Fragrance', 'Active', 'Other']

function normalize(data) {
  const list = data?.ingredients
  if (!Array.isArray(list)) throw new Error('The server returned an unexpected response.')
  const ingredients = list.map((i) => {
    const o = typeof i === 'string' ? { name: i } : i
    return {
      name: o.name || o.ingredient || 'Unknown',
      category: CATS.includes(o.category) ? o.category : o.category ? 'Other' : null,
      function: o.function || null,
      explanation: o.explanation || o.description || null,
      benefits: o.benefits || [],
      concerns: o.concerns || [],
      source: o.source || null,
    }
  })
  return { text: data.text || data.extracted_text || data.raw_text || '', ingredients, demo: false }
}

export async function analyzeImage(file, signal) {
  const body = new FormData()
  body.append(FIELD, file)
  let res
  try {
    res = await fetch(API_URL + ENDPOINT, { method: 'POST', body, signal })
  } catch (e) {
    if (e.name === 'AbortError') throw e
    throw new Error('Could not reach the analysis server. Is the backend running?')
  }
  if (!res.ok) throw new Error(`Server error (${res.status}). Please try another image.`)
  return normalize(await res.json().catch(() => null))
}

// DEMO ONLY: static sample data, never presented as real OCR output.
export function demoResult() {
  const I = (name, category, fn, explanation, benefits = [], concerns = []) => ({
    name, category, function: fn, explanation, benefits, concerns, source: 'Demo sample',
  })
  return {
    demo: true,
    text: 'Aqua, Glycerin, Niacinamide, Caprylic/Capric Triglyceride, Cetearyl Alcohol, Panthenol, Phenoxyethanol, Parfum',
    ingredients: [
      I('Aqua', 'Other', 'Solvent', 'Water, the base of most formulas.'),
      I('Glycerin', 'Humectant', 'Draws in moisture', 'Helps skin hold water.', ['Hydration']),
      I('Niacinamide', 'Active', 'Skin-conditioning', 'A form of vitamin B3.', ['Supports barrier', 'Evens tone'], ['Rarely, flushing at high levels']),
      I('Caprylic/Capric Triglyceride', 'Emollient', 'Softens skin', 'Light oil derived from coconut and glycerin.', ['Softness']),
      I('Cetearyl Alcohol', 'Emollient', 'Texture and softening', 'A fatty alcohol, not drying like ethanol.', ['Creamy feel']),
      I('Panthenol', 'Active', 'Soothing', 'Provitamin B5.', ['Comfort', 'Hydration']),
      I('Phenoxyethanol', 'Preservative', 'Prevents microbial growth', 'Common preservative used at low levels.', [], ['May irritate very sensitive skin']),
      I('Parfum', 'Fragrance', 'Scent', 'A blend of undisclosed fragrance components.', [], ['Possible sensitivity for fragrance-sensitive skin']),
    ],
  }
}
export { CATS }