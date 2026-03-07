
import Navbar from "@/components/Navbar"
import Hero from "@/components/Hero"
import Services from "@/components/Services"
import ContactForm from "@/components/ContactForm"
import Map from "@/components/Map"
import Footer from "@/components/Footer"
import Reviews from "@/components/Reviews"

export default function Home(){

return(

<main>

<Navbar/>
<Hero/>
<Services/>
<Reviews/>

<section id="contact" className="py-20 max-w-6xl mx-auto grid md:grid-cols-2 gap-10">

<div>
<h3 className="text-3xl font-bold mb-6">
Request an Appraisal Quote
</h3>

<ContactForm/>
</div>

<Map/>

</section>

<Footer/>

</main>

)

}
