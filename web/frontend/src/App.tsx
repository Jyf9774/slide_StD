import { BrowserRouter, Routes, Route } from "react-router-dom"
import { Layout } from "@/components/Layout"
import { DashboardPage } from "@/pages/DashboardPage"
import { ProcessPage } from "@/pages/ProcessPage"
import { ResultPage } from "@/pages/ResultPage"

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/process" element={<ProcessPage />} />
          <Route path="/result/:slideName" element={<ResultPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
