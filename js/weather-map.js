import { STATIONS, METRICS, latestByStation, latestDates, rowsOn, temperatureMoves,
  formatNumber, formatMetric, formatDelta, create } from './common.js';

// x/y are the airport coordinates projected in the same Albers equal-area frame as conus.svg.
const airports = {
  KXNA: [539.2, 357.9, 36.2819, -94.3068],
  KLIT: [576.8, 390.9, 34.7294, -92.2243],
  KDFW: [490.9, 432.2, 32.8998, -97.0403],
  KIAH: [522.3, 495.8, 29.9902, -95.3368],
  KORD: [639.6, 227.7, 41.9742, -87.9073],
  KJFK: [870.2, 220.1, 40.6413, -73.7781],
  KLAX: [112.1, 362.4, 33.9416, -118.4085],
  KDEN: [366.5, 273.1, 39.8561, -104.6737],
  KMIA: [819.2, 561.1, 25.7959, -80.287],
  KSEA: [125.3, 60.3, 47.4502, -122.3088],
  KBOS: [904.3, 172.5, 42.3656, -71.0096],
  KATL: [717.4, 403.5, 33.6407, -84.4277],
};
const routes = [
  ['KSEA', 'KDEN'], ['KLAX', 'KDFW'], ['KJFK', 'KORD'], ['KDEN', 'KDFW'],
  ['KDFW', 'KATL'], ['KORD', 'KXNA'], ['KBOS', 'KATL'], ['KATL', 'KMIA'],
  ['KIAH', 'KLIT'], ['KLIT', 'KXNA']
];
const byId = id => document.getElementById(id);
function svg(tag, attributes, parent) {
  const element = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [name, value] of Object.entries(attributes)) element.setAttribute(name, value);
  parent.append(element);
  return element;
}
function tempColor(t) {
  if (t == null) return '#87929a';
  if (t < 40) return '#78a4e6';
  if (t < 50) return '#abd3ec';
  if (t < 65) return '#e0ddd0';
  return t < 80 ? '#eac083' : '#e59867';
}
function reading(parent, label, value, secondary = '') {
  const block = create('div', 'reading');
  block.append(create('small', '', label), create('strong', '', value));
  if (secondary) block.append(create('span', '', secondary));
  parent.append(block);
}
function drawRoutes() {
  routes.forEach(([start, end], index) => {
    const [x,y] = airports[start], [u,v] = airports[end];
    const d = `M${x} ${y} Q${(x+u)/2} ${(y+v)/2-Math.abs(u-x)*.22-12} ${u} ${v}`;
    svg('path', {d, 'data-route': start+' '+end}, byId('routes'));
    if (index >= 3) return;
    const plane = svg('g', {}, byId('planes'));
    svg('path', {d:'M9 0 Q9 -1 6 -1.3 L2 -1.5 -3 -8 -5 -8 -3 -1.5 -7 -1 -9 -3 -10 -3 -9 0 -10 3 -9 3 -7 1 -3 1.5 -5 8 -3 8 2 1.5 6 1.3Z'}, plane);
    svg('animateMotion', {path:d, dur:(42+index*9)+'s', begin:-(12+index*7)+'s', rotate:'auto', repeatCount:'indefinite'}, plane);
  });
  const map = byId('network'), motion = matchMedia('(prefers-reduced-motion: reduce)');
  function sync() {
    if (motion.matches || document.hidden) map.pauseAnimations();
    else map.unpauseAnimations();
  }
  sync();
  motion.addEventListener('change', sync);
  document.addEventListener('visibilitychange', sync);
}
function sparkline(panel, history, id) {
  const series = history.filter(row => row.item_id === id && row.temperature_f != null)
    .sort((a,b) => a.date.localeCompare(b.date));
  if (series.length < 2) return;
  const values = series.map(row => row.temperature_f);
  const low = Math.min(...values), span = Math.max(...values)-low || 1;
  const dates = series.map(row => Date.parse(row.date));
  const chart = svg('svg', {viewBox:'0 0 120 30',class:'spark', role:'img',
    'aria-label': 'Temperature history, '+series[0].date+' to '+series.at(-1).date}, panel);
  const points = values.map((v,i) => [2+116*(dates[i]-dates[0])/(dates.at(-1)-dates[0] || 1),26-22*(v-low)/span]);
  svg('polyline', {points:points.join(' '), fill:'none',stroke:'currentColor','stroke-width':2},chart);
  const [cx,cy] = points.at(-1);
  svg('circle', {cx,cy,r:2.4,fill:'currentColor'},chart);
  panel.append(create('small','spark-context',series[0].date.slice(5)+' → '+series.at(-1).date.slice(5)+' · °F'));
}
// Fixed decorative geometry in map coordinates. Each path includes two side branches.
function drawLightning() {
  const flashes = [
    [220, 160, 'M0 0 l12 16 -6 4 17 12 -4 8 20 16 M12 16 l12 1 10 8 M23 32 l-12 3 -7 10'],
    [498, 200, 'M0 0 l-8 15 5 5 -15 14 5 4 -14 18 M-8 15 l-12 4 -7 8 M-18 34 l9 5 4 9'],
    [738, 307, 'M0 0 l10 14 -4 8 14 10 -2 6 15 14 M10 14 l11 -2 10 7 M20 32 l-10 7 -2 8']
  ];
  flashes.forEach(([x, y, d], index) => {
    svg('path', {d, transform:`translate(${x} ${y})`, style:`--flash-delay:${180 + index * 510}ms`}, byId('lightning'));
  });
}
function startClock() {
  const clock = byId('utc-clock');
  function tick() {
    const instant = new Date().toISOString();
    clock.dateTime = instant;
    clock.textContent = instant.slice(11, 19) + ' UTC';
  }
  tick();
  setInterval(tick, 1000);
}
export function initMap({history,status}) {
  const {latest} = latestDates(history), current = rowsOn(history,latest), saved = latestByStation(history);
  const moves = temperatureMoves(history), changes = new Map(moves.map(m => [m.id,m.change]));
  const sorted = [...current.values()].filter(r=>r.temperature_f != null).sort((a,b)=>a.temperature_f-b.temperature_f);
  const strip = byId('national-summary');
  reading(strip,'Reporting',current.size+' / '+STATIONS.length);
  for (const [label,row] of [['Warmest',sorted.at(-1)],['Coldest',sorted[0]]]) {
    reading(strip,label,row ? formatNumber(row.temperature_f)+'°F' : '—',row?.item_id);
  }
  reading(strip,'Biggest move',formatDelta(moves[0]?.change),moves[0]?.id);
  reading(strip,'History',new Set(history.map(r=>r.date)).size+' days');
  drawRoutes();
  drawLightning();
  startClock();
  for (const {id,name} of STATIONS) {
    const [x,y] = airports[id], t = current.get(id)?.temperature_f;
    const node = svg('g',{class:'beacon',transform:`translate(${x} ${y})`,tabindex:0,role:'button',
      'aria-label':id+' '+name,'data-station':id,style:`color:${tempColor(t)};--delay:${x}ms`},byId('nodes'));
    const change = formatDelta(changes.get(id));
    const observation = t == null ? 'No temperature' : formatNumber(t)+'°F';
    const comparison = change === '—' ? 'No prior comparison' : change+' vs prior';
    node.setAttribute('aria-label', [id, name, observation, comparison].join(', '));
    function showTip() {
      const tip = byId('airport-tip');
      tip.replaceChildren(create('strong', '', id), create('span', '', name),
        create('span', '', observation+' · '+comparison));
      tip.hidden = false;
    }
    function hideTip() { byId('airport-tip').hidden = true; }
    node.onmouseenter = node.onfocus = showTip;
    node.onmouseleave = () => { if (document.activeElement !== node) hideTip(); };
    node.onblur = hideTip;
    svg('circle',{r:20,fill:'transparent'},node);
    svg('circle',{r:11,class:'halo'},node);
    svg('circle',{r:6,class:'ring'},node);
    svg('circle',{r:2.7,fill:'currentColor'},node);
    const left = ['KXNA','KDFW','KJFK'].includes(id);
    const label = svg('text',{x:left?-13:13,y:4,'text-anchor':left?'end':'start'},node);
    label.textContent=id;
    svg('tspan',{x:left?-13:13,dy:15,class:'map-temp'},label).textContent=t == null?'—':Math.round(t)+'°';
    node.onkeydown = e => {if (['Enter',' '].includes(e.key)){e.preventDefault(); select(id);}};
  }
  function select(id) {
    document.querySelectorAll('[data-station]').forEach(el => {
      el.classList.toggle('selected',el.dataset.station===id);
      if(el.matches('.beacon')) el.setAttribute('aria-pressed',String(el.dataset.station===id));
    });
    byId('network').classList.toggle('has-selection',Boolean(id));
    document.querySelectorAll('[data-route]').forEach(el=>el.classList.toggle('connected',el.dataset.route.split(' ').includes(id)));
    const panel=byId('station-detail');
    panel.replaceChildren();
    if (!id) {panel.append(create('p','','Select an airport to inspect its observation history.'));return;}
    const row=saved.get(id), station=STATIONS.find(s=>s.id===id);
    const info=create('div','station-title');
    info.append(create('small','',id),create('h2','',station.name),create('span','',airports[id][2].toFixed(2)+'° N · '+Math.abs(airports[id][3]).toFixed(2)+'° W'));
    panel.append(info);
    const values=create('div','station-values');
    reading(values,'Temperature',row?.temperature_f == null?'—':formatNumber(row.temperature_f)+'°F',formatDelta(changes.get(id))+' vs prior date');
    for (const metric of METRICS.slice(1)) reading(values,metric.title, row?.[metric.key] == null?'—':formatMetric(row[metric.key],metric.key)+' '+metric.unit);
    const source=status?.sources?.find(s=>s.name===id);
    reading(values,'Latest',row?.date || '—',source ? source.ok?'Source healthy':'Fetch failed':'Source unknown');
    panel.append(values);
    sparkline(info,history,id);
    const close=create('button','close','Clear selection');
    close.onclick=()=>{select(null);document.querySelector('.beacon[data-station="'+id+'"]').focus();};
    panel.append(close);
  }
  document.querySelectorAll('[data-station]').forEach(el=>el.onclick=()=>select(el.dataset.station));
  select(null);
  let timeout;
  byId('map-pulse').onclick=()=>{
    const atlas=document.querySelector('.atlas');
    atlas.classList.remove('scanning');
    void atlas.offsetWidth;
    atlas.classList.add('scanning');
    clearTimeout(timeout);
    timeout=setTimeout(()=>atlas.classList.remove('scanning'),1750);
  };
}
