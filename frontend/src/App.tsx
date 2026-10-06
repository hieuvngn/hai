import { BrowserRouter, Route, Routes, useParams } from "react-router-dom";
import { ChatPage } from "@/pages/ChatPage";
import { AdminPage } from "@/pages/AdminPage";

function ProductRoute() {
  const { id } = useParams<{ id: string }>();
  return <ChatPage initialProductId={id} />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ChatPage />} />
        <Route path="/products/:id" element={<ProductRoute />} />
        <Route path="/admin" element={<AdminPage />} />
      </Routes>
    </BrowserRouter>
  );
}
