
export default function Navbar() {
  return (
    <header className="shadow bg-white">
      <div className="max-w-7xl mx-auto flex justify-between p-5">
        <h1 className="font-bold text-xl">Appraisal Quest Co.</h1>

        <nav className="flex gap-6 text-sm">
          <a href="#services">Services</a>
          <a href="#contact">Contact</a>
          <a href="tel:8054693088" className="bg-blue-700 text-white px-4 py-2 rounded">
            Call Now
          </a>
        </nav>
      </div>
    </header>
  );
}
