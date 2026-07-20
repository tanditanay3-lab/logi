import { Routes, Route } from 'react-router-dom'
import { HomePage } from './pages/HomePage'
import { PricingPage } from './pages/PricingPage'
import { FeaturesPage } from './pages/FeaturesPage'
import { ContactPage } from './pages/ContactPage'
import { Navbar } from './components/Navbar'
import { Footer } from './components/Footer'

function App() {
  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/pricing" element={<PricingPage />} />
          <Route path="/features" element={<FeaturesPage />} />
          <Route path="/contact" element={<ContactPage />} />
        </Routes>
      </main>
      <Footer />
    </div>
  )
}

export default App
