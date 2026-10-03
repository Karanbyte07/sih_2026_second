import {Routes,Route,Navigate} from 'react-router-dom';import {useApp} from './context.jsx';import Layout from './components/Layout.jsx';
import Login from './pages/Login.jsx';import Overview from './pages/Overview.jsx';import DigitalTwin from './pages/DigitalTwin.jsx';import Infrastructure from './pages/Infrastructure.jsx';
import Energy from './pages/Energy.jsx';import Logistics from './pages/Logistics.jsx';import Environment from './pages/Environment.jsx';import AIAnalytics from './pages/AIAnalytics.jsx';
import Simulation from './pages/Simulation.jsx';import Alerts from './pages/Alerts.jsx';import Maintenance from './pages/Maintenance.jsx';import SettingsPage from './pages/Settings.jsx';
export default function App(){const {user}=useApp();
  return <Routes><Route path="/login" element={user?<Navigate to="/"/>:<Login/>}/>
    <Route element={user?<Layout/>:<Navigate to="/login"/>}>
      <Route index element={<Overview/>}/><Route path="twin" element={<DigitalTwin/>}/><Route path="infrastructure" element={<Infrastructure/>}/><Route path="energy" element={<Energy/>}/>
      <Route path="logistics" element={<Logistics/>}/><Route path="environment" element={<Environment/>}/><Route path="ai" element={<AIAnalytics/>}/><Route path="simulation" element={<Simulation/>}/>
      <Route path="alerts" element={<Alerts/>}/><Route path="maintenance" element={<Maintenance/>}/><Route path="settings" element={<SettingsPage/>}/></Route>
    <Route path="*" element={<Navigate to="/"/>}/></Routes>}
