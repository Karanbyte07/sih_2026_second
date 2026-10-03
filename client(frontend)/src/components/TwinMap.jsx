const COLORS={normal:['#d4f5e6','#3fbf8f'],warning:['#fff1bf','#d9a91f'],critical:['#ffd3dc','#e8607f'],offline:['#e4e3ee','#8d8aa8']};
const ICON={generator:'⚡',battery:'🔋',heating:'🔥',water:'💧',living:'🏠',lab:'🔬',comms:'📡',fuel:'⛽'};
export default function TwinMap({assets,selected,onSelect,dir=200,compact}){
  const by=Object.fromEntries(assets.map(a=>[a.id,a])),c=a=>[a.x+a.w/2,a.y+a.h/2];
  return <svg viewBox="0 0 100 56" className={`twin ${compact?'compact':''}`}>
    {assets.flatMap(a=>a.links.map(l=>{const b=by[l];if(!b)return null;const [x1,y1]=c(a),[x2,y2]=c(b);
      return <line key={a.id+l} x1={x1} y1={y1} x2={x2} y2={y2} className={`link ${a.status!=='normal'||b.status!=='normal'?'hot':''}`}/>}))}
    {assets.map(a=>{const [bg,fg]=COLORS[a.status]||COLORS.normal,sel=selected===a.id,r=a.readings[0];
      return <g key={a.id} className={`node ${a.status}`} onClick={()=>onSelect?.(a.id)} style={{cursor:onSelect?'pointer':'default'}}>
        <rect x={a.x} y={a.y} width={a.w} height={a.h} rx="1.8" fill={bg} stroke={fg} strokeWidth={sel?1:.45}/>
        <text x={a.x+1.4} y={a.y+4.4} fontSize="3">{ICON[a.type]}</text>
        <text x={a.x+5.2} y={a.y+4.2} fontSize="2" fontWeight="700">{a.name}</text>
        {!compact&&r&&<text x={a.x+1.4} y={a.y+a.h-1.6} fontSize="1.8">{r.k}: {r.v}{r.u}</text>}</g>})}
    <g transform="translate(91 14)"><circle r="6" fill="#fff" stroke="#cfc6ee" strokeWidth=".4"/><text y="-6.8" textAnchor="middle" fontSize="1.8">N</text>
      <g style={{transform:`rotate(${dir}deg)`,transition:'transform 1s'}}><path d="M0-4.6L1.3 1.4 0 .4-1.3 1.4Z" fill="#8b6fe0"/></g><text y="9.4" textAnchor="middle" fontSize="1.7">wind</text></g>
  </svg>}
