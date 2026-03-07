
export default function Services() {

const services = [
"Estate Appraisals",
"Divorce Appraisals",
"Date of Death Valuations",
"Pre-Listing Appraisals",
"Relocation Appraisals",
"Foreclosure / REO Appraisals"
]

return (

<section id="services" className="py-20 max-w-6xl mx-auto">

<h3 className="text-3xl font-bold text-center mb-12">
Appraisal Services
</h3>

<div className="grid md:grid-cols-3 gap-6">

{services.map((service)=>(
<div key={service} className="border p-6 rounded shadow-sm">
{service}
</div>
))}

</div>
</section>

)
}
