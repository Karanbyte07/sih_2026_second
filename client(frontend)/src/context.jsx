import {createContext,useContext,useEffect,useState} from 'react';import {setSess} from './api.js';
const Ctx=createContext();export const useApp=()=>useContext(Ctx);
const load=(k,d)=>{try{return JSON.parse(localStorage.getItem(k))??d}catch{return d}};
const PERM={admin:['*'],ops:['ack','simulate'],maintenance:['maintenance','ack'],logistics:['inventory']};
export function AppProvider({children}){
  const [user,setUser]=useState(()=>load('atw_user',null));
  const [station,setStation]=useState(()=>load('atw_station','maitri'));
  const [theme,setTheme]=useState(()=>load('atw_theme','light'));
  setSess(user);
  useEffect(()=>{localStorage.setItem('atw_user',JSON.stringify(user))},[user]);
  useEffect(()=>{localStorage.setItem('atw_station',JSON.stringify(station))},[station]);
  useEffect(()=>{localStorage.setItem('atw_theme',JSON.stringify(theme));document.documentElement.dataset.theme=theme},[theme]);
  useEffect(()=>{if(user&&!user.stations.includes(station))setStation(user.stations[0])},[user,station]);
  const can=a=>{const p=PERM[user?.role]||[];return p.includes('*')||p.includes(a)};
  return <Ctx.Provider value={{user,login:setUser,logout:()=>setUser(null),station,setStation,theme,setTheme,can}}>{children}</Ctx.Provider>}
