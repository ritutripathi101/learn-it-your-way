import { useMemo } from 'react'
import katex from 'katex'
import 'katex/dist/katex.min.css'

// $$display$$, \[display\], \(inline\), $inline$ (no space just inside the dollar signs, so "$5 and $10" stays text)
const MATH = /\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\]|\\\(([\s\S]+?)\\\)|\$([^\s$](?:[^$\n]*?[^\s$])?)\$/g

export default function RichText({ text = '' }) {
  const parts = useMemo(() => {
    const source = String(text)
    const out = []
    let last = 0
    for (const m of source.matchAll(MATH)) {
      if (m.index > last) out.push({ math: false, value: source.slice(last, m.index) })
      const display = m[1] !== undefined || m[2] !== undefined
      const tex = m[1] ?? m[2] ?? m[3] ?? m[4]
      try {
        out.push({ math: true, value: katex.renderToString(tex, { displayMode: display, throwOnError: true, trust: false }) })
      } catch {
        out.push({ math: false, value: m[0] })
      }
      last = m.index + m[0].length
    }
    if (last < source.length) out.push({ math: false, value: source.slice(last) })
    return out
  }, [text])
  return <>{parts.map((p, i) => p.math ? <span key={i} dangerouslySetInnerHTML={{ __html: p.value }} /> : <span key={i}>{p.value}</span>)}</>
}
