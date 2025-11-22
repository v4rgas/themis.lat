import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Landing } from './pages/Landing'
import { Explore } from './pages/Explore'
import { Detail } from './pages/Detail'
import './App.css'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/explore" element={<Explore />} />
        <Route path="/detail" element={<Detail />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
