"""Optional developer command; deployed package already includes the built files."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "frontend"
analytics = (ROOT / "analytics.mjs").read_text("utf-8").replace("export ", "")
app = (ROOT / "app.js").read_text("utf-8").split("\n", 1)[1]
app = app.replace("window.scrollTo(0,0)", "scrollTop()")
app = app.replace("history.replaceState(null,'','#'+state.page);", "")
app = app.replace("<small>Özel erişim</small>", "<small>TSB açık verileri</small>")
app = app.replace("if(state.cache[key]&&!refresh)return state.cache[key];", "if(state.cache[key]&&!refresh&&checked.has(key))return state.cache[key];")
app = app.replace("state.cache[key]=d;return d", "state.cache[key]=d;checked.add(key);return d")
app = app.replace("await fetchData(pk);state.previous=pk;", "try{await fetchData(pk);state.previous=pk;}catch(e){state.previous=key;toast('Önceki yıl verisi alınamadı; karşılaştırma dönemini ayrıca seçebilirsiniz.');}")
# Opening uses the six-hour server cache; the explicit refresh button bypasses it.
start = app.index("async function init()")
app = app[:start] + app[start:].replace("fetchData(state.current,true)", "fetchData(state.current)").replace("fetchData(state.previous,true)", "fetchData(state.previous)")
app = "const checked=new Set();\n" + app
bridge = (ROOT / "bridge.js").read_text("utf-8")
(ROOT / "component.js").write_text(bridge.replace("/* ANALYTICS */", analytics).replace("/* APP */", app), "utf-8")
css = (ROOT / "style.css").read_text("utf-8") + (ROOT / "readability.css").read_text("utf-8")
css = css.replace(":root", ":host").replace("body{", ":host{")
css += "\n:host{display:block;min-width:0} .topbar{padding-right:110px}\n@media(max-width:700px){.topbar{padding-right:16px;padding-top:36px;height:auto;min-height:110px}}\n"
(ROOT / "component.css").write_text(css, "utf-8")
