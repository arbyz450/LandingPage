
import { NextResponse } from "next/server"
import { Resend } from "resend"

const resend = new Resend(process.env.RESEND_API_KEY)

export async function POST(req: Request) {

const body = await req.json()

const {name,email,phone,message} = body

await resend.emails.send({

from: "Appraisal Quest <leads@appraisalquest.com>",

to: process.env.LEAD_EMAIL as string,

subject: "New Appraisal Quote Request",

html: `
<h2>New Lead</h2>

<p><strong>Name:</strong> ${name}</p>
<p><strong>Email:</strong> ${email}</p>
<p><strong>Phone:</strong> ${phone}</p>

<p><strong>Message:</strong></p>
<p>${message}</p>
`
})

return NextResponse.json({success:true})

}
