import { BarChart3, CalendarDays, CirclePlus, Megaphone, MoreHorizontal } from 'lucide-react'

const stats = [
  ['Каналы', '0'], ['Запланировано', '0'], ['На согласовании', '0'], ['Доход за месяц', '0 ₽'],
]

export default function App() {
  return <div className="app">
    <header><div><span className="eyebrow">РАБОЧЕЕ ПРОСТРАНСТВО</span><h1>ChannelDesk</h1></div><button className="workspace">Создать агентство</button></header>
    <main>
      <section className="hero"><p>Управляйте каналами, рекламой и командой, не выходя из Telegram.</p><button><CirclePlus size={19}/> Создать рабочее пространство</button></section>
      <section className="stats">{stats.map(([label,value])=><article key={label}><span>{label}</span><strong>{value}</strong></article>)}</section>
      <section className="panel"><div className="panel-title"><h2>Сегодня</h2><CalendarDays size={20}/></div><div className="empty"><div className="empty-icon"><Megaphone/></div><h3>Публикаций пока нет</h3><p>После подключения канала здесь появится расписание команды.</p></div></section>
    </main>
    <nav>{[[BarChart3,'Обзор'],[CalendarDays,'Календарь'],[CirclePlus,'Создать'],[Megaphone,'Реклама'],[MoreHorizontal,'Ещё']].map(([Icon,label],i)=>{const C=Icon as typeof BarChart3;return <button className={i===0?'active':''} key={label as string}><C size={21}/><span>{label as string}</span></button>})}</nav>
  </div>
}
