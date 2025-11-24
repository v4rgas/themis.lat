import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Landing } from './pages/Landing'
import { Explore } from './pages/Explore'
import { Detail } from './pages/Detail'
import { Wishlisted } from './pages/Wishlisted'
import './App.css'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/explore" element={<Explore />} />
        <Route path="/detail" element={<Detail />} />
        <Route path="/wishlisted" element={<Wishlisted />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
