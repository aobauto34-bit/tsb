// Streamlit v2 reruns update this controller without resetting the dashboard.
export default function(component) {
  const root = component.parentElement;
  if (root.__pusula) {
    root.__pusula.send = component.setTriggerValue;
    root.__pusula.receive(component.data.reply);
    return;
  }
  const bridge = root.__pusula = {send: component.setTriggerValue, queue: [], active: null};
  const base = component.data.bootstrap;
  bridge.next = () => {
    if (bridge.active || !bridge.queue.length) return;
    bridge.active = bridge.queue.shift();
    bridge.send('request', bridge.active.request);
  };
  bridge.receive = reply => {
    if (!reply || reply.id !== bridge.active?.request.id) return;
    const task = bridge.active;
    bridge.active = null;
    clearTimeout(task.timer);
    task.resolve({ok: reply.ok, json: async () => reply.body});
    bridge.next();
  };
  const fetch = async path => {
    if (path === '/api/bootstrap') return {ok:true, json:async () => base};
    const url = new URL(path, 'https://sigorta-pusula.local');
    const kind = url.pathname === '/api/catalog' ? 'catalog' : url.pathname === '/api/data' ? 'data' : null;
    if (!kind) throw Error('Desteklenmeyen veri isteği.');
    return new Promise((resolve,reject) => {
      const request = {id:crypto.randomUUID(),kind,period:url.searchParams.get('period'),refresh:url.searchParams.get('refresh')==='1'};
      const task = {request,resolve,reject};
      task.timer = setTimeout(() => {
        bridge.queue = bridge.queue.filter(x => x !== task);
        if (bridge.active === task) bridge.active = null;
        reject(Error('TSB yanıt süresi aşıldı. Yenile düğmesiyle tekrar deneyin.'));
        bridge.next();
      }, 300000);
      bridge.queue.push(task);
      bridge.next();
    });
  };
  const document = {
    querySelector: selector => root.querySelector(selector),
    querySelectorAll: selector => root.querySelectorAll(selector),
    addEventListener: (...args) => root.addEventListener(...args),
    createElement: (...args) => globalThis.document.createElement(...args),
    set title(value) { globalThis.document.title = value; }
  };
  const scrollTop = () => globalThis.document.querySelector('[data-testid="stMain"]')?.scrollTo(0,0);
  // Build script inserts the same tested financial logic and the dashboard here.
  /* ANALYTICS */
  /* APP */
}
