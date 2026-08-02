import { useEffect,useState } from 'react'
import { BarChart3,CalendarDays,CirclePlus,Megaphone,MoreHorizontal,Radio,RefreshCw } from 'lucide-react'
import { api,type Workspace,type Pending,type Channel } from './api'

export default function App(){
 const [spaces,setSpaces]=useState<Workspace[]>([]),[active,setActive]=useState<Workspace|null>(null),[pending,setPending]=useState<Pending[]>([]),[channels,setChannels]=useState<Channel[]>([]),[name,setName]=useState('Моё агентство'),[error,setError]=useState(''),[loading,setLoading]=useState(true)
 async function load(){setLoading(true);setError('');try{const s=await api.workspaces();setSpaces(s);const a=active||s[0]||null;setActive(a);const [p,c]=await Promise.all([api.pending(),a?api.channels(a.id):Promise.resolve([])]);setPending(p);setChannels(c)}catch(e){setError(e instanceof Error?e.message:'Ошибка загрузки')}finally{setLoading(false)}}
 useEffect(()=>{load()},[])
 async function create(){try{const w=await api.createWorkspace(name);setSpaces([w,...spaces]);setActive(w);setError('')}catch(e){setError(e instanceof Error?e.message:'Ошибка') }}
 async function connect(id:number){if(!active)return;try{await api.connect(active.id,id);await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка подключения')}}
 return <div className="app"><header><div><span className="eyebrow">РАБОЧЕЕ ПРОСТРАНСТВО</span><h1>ChannelDesk</h1></div><button className="workspace" onClick={load}><RefreshCw size={15}/></button></header><main>
  {error&&<section className="panel" style={{color:'#ff9b9b',marginBottom:12}}>{error}</section>}
  {!active&&!loading?<section className="hero"><p>Создайте рабочее пространство агентства.</p><input value={name} onChange={e=>setName(e.target.value)} style={{width:'100%',padding:13,borderRadius:12,border:'1px solid #445',background:'#111722',color:'white',marginBottom:12}}/><button onClick={create}><CirclePlus size={19}/> Создать</button></section>:<>
   <section className="hero"><span className="eyebrow">{active?.role}</span><p style={{marginTop:8}}>{active?.name}</p><div>{spaces.length>1&&<select value={active?.id} onChange={e=>setActive(spaces.find(x=>x.id===Number(e.target.value))||null)}>{spaces.map(w=><option key={w.id} value={w.id}>{w.name}</option>)}</select>}</div></section>
   {pending.length>0&&<section className="panel" style={{marginTop:16}}><div className="panel-title"><h2>Обнаруженные каналы</h2><Radio size={20}/></div>{pending.map(p=><article key={p.id} style={{padding:'14px 0',borderBottom:'1px solid #252b36'}}><strong>{p.title}</strong><p style={{color:'#8d96a8',fontSize:12}}>{p.bot_permissions.can_post_messages?'Публикация разрешена':'Нет права публикации'}</p><button onClick={()=>connect(p.id)} disabled={!p.bot_permissions.can_post_messages}>Подключить</button></article>)}</section>}
   <section className="stats"><article><span>Каналы</span><strong>{channels.length}</strong></article><article><span>Запланировано</span><strong>0</strong></article><article><span>На согласовании</span><strong>0</strong></article><article><span>Доход</span><strong>0 ₽</strong></article></section>
   <section className="panel"><div className="panel-title"><h2>Каналы</h2><CalendarDays size={20}/></div>{channels.length?channels.map(c=><div key={c.id} style={{padding:'15px 0',borderBottom:'1px solid #252b36'}}><strong>{c.title}</strong><div style={{color:'#72d99f',fontSize:12}}>● подключён</div></div>):<div className="empty"><div className="empty-icon"><Megaphone/></div><h3>Каналов пока нет</h3><p>Добавьте бота администратором канала и обновите экран.</p></div>}</section>
  </>}
 </main><nav>{[[BarChart3,'Обзор'],[CalendarDays,'Календарь'],[CirclePlus,'Создать'],[Megaphone,'Реклама'],[MoreHorizontal,'Ещё']].map(([Icon,label],i)=>{const C=Icon as typeof BarChart3;return <button className={i===0?'active':''} key={label as string}><C size={21}/><span>{label as string}</span></button>})}</nav></div>
}
