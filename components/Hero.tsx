
export default function Hero() {
  return (
    <section className="bg-blue-900 text-white py-24 text-center">
      <h2 className="text-4xl font-bold mb-6">
        Ventura County Certified Home Appraiser
      </h2>

      <p className="max-w-xl mx-auto mb-8">
        Professional residential property appraisals by Daniel Rocha.
      </p>

      <div className="flex justify-center gap-6">
        <a href="#contact" className="bg-white text-blue-900 px-6 py-3 rounded">
          Get Fee Quote
        </a>

        <a href="tel:8054693088" className="bg-blue-600 px-6 py-3 rounded">
          Call (805) 469-3088
        </a>
      </div>
    </section>
  );
}
