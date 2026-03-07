
"use client"
import { useState } from "react"

export default function ContactForm(){

const [sent,setSent] = useState(false)

async function submit(e:any){
e.preventDefault()

const form = new FormData(e.target)

await fetch("/api/contact",{
method:"POST",
body:JSON.stringify(Object.fromEntries(form))
})

setSent(true)
}

if(sent) return <p className="text-green-600">Message sent.</p>

return(

<form onSubmit={submit} className="space-y-4 max-w-xl">

<input name="name" placeholder="Name" required className="border p-3 w-full"/>

<input name="email" placeholder="Email" required className="border p-3 w-full"/>

<input name="phone" placeholder="Phone" className="border p-3 w-full"/>

<textarea name="message" placeholder="Tell us about the appraisal you need" className="border p-3 w-full"/>

<button className="bg-blue-800 text-white px-6 py-3 rounded">
Request Quote
</button>

</form>

)
}
