< !DOCTYPE
html >
< html
lang = "en" >
< head >
< meta
charset = "UTF-8" >
< meta
name = "viewport"
content = "width=device-width, initial-scale=1.0" >
< title > Studio
Booking & Payment < / title >
< style >
body
{font - family: Arial, sans - serif;
background - color:  # F5F5DC; color: #3E2723; margin: 0; padding: 20px; }
.container
{max - width: 550px;
background: white;
padding: 25
px;
border - radius: 12
px;
margin: 0
auto;
box - shadow: 0
4
px
10
px
rgba(0, 0, 0, 0.1);}
h2
{text - align: center;
color:  # 3E2723; }
.form - group
{margin - bottom: 15px;}
label
{font - weight: bold;
display: block;
margin - bottom: 5
px;}
input, select, button
{width: 100 %;
padding: 10
px;
border - radius: 6
px;
border: 1
px
solid  # ccc; box-sizing: border-box; }
button
{background - color:  # D2B48C; color: #3E2723; font-weight: bold; border: none; cursor: pointer; margin-top: 10px; }
     button: hover
{background - color:  # c19a6b; }
.payment - box
{
    background:  # fdf8f0; border: 1px dashed #D2B48C; padding: 15px; border-radius: 8px; text-align: center; margin-top: 15px; }
.qr - placeholder
{
    background:  # e0e0e0; width: 180px; height: 180px; margin: 10px auto; display: flex; align-items: center; justify-content: center; font-weight: bold; border-radius: 8px; }
.hidden
{display: none;}
.total - summary
{font - size: 1.1em;
font - weight: bold;
background:  # eef7ee; color: #2E7D32; padding: 10px; border-radius: 6px; text-align: center; }
< / style >
    < / head >
        < body >

        < div


class ="container" >

< h2 > Studio
Booking
Form < / h2 >

< !-- STEP
1: BOOKING
FORM -->
< form
id = "bookingForm" >
< div


class ="form-group" >

< label > Date: < / label >
< input
type = "date"
id = "date"
required
onchange = "fetchSlots()" >
< / div >

< div


class ="form-group" >

< label > Schedule
Slot: < / label >
< select
id = "schedule"
required >
< option
value = "" > -- Select
Date
First - - < / option >
< / select >
< / div >

< div


class ="form-group" >

< label > Customer
Name: < / label >
< input
type = "text"
id = "customer_name"
required >
< / div >

< div


class ="form-group" >

< label > Contact
Number: < / label >
< input
type = "text"
id = "contact_no"
required >
< / div >

< div


class ="form-group" >

< label > Package: < / label >
< select
id = "package"
required
onchange = "calculateTotal()" >
< option
value = "Solo" > Solo - ₱249 < / option >
< option
value = "Duo" > Duo - ₱399 < / option >
< option
value = "Squad" > Squad - ₱599 < / option >
< option
value = "Party" > Party - ₱999 < / option >
< / select >
< / div >

< div


class ="form-group" >

< label > Package
Type: < / label >
< select
id = "package_type"
required >
< option
value = "Starter" > Starter < / option >
< option
value = "Upgraded" > Upgraded < / option >
< / select >
< / div >

< div


class ="total-summary" >


Downpayment
Due(50 %): ₱ < span
id = "dp_amount" > 124.50 < / span >
< / div >

< button
type = "submit" > Proceed
to
Payment → < / button >
< / form >

< !-- STEP
2: PAYMENT & RECEIPT
UPLOAD -->
< div
id = "paymentSection"


class ="hidden" >

< h3 > GCash
Downpayment
Confirmation < / h3 >
< p > Please
pay
the
50 % downpayment
to
lock
your
reservation
slot. < / p >

< div


class ="payment-box" >

< div > < strong > GCash
Account: < / strong > 0
917 - XXX - XXXX < / div >
< div > < strong > Account
Name: < / strong > Photo
Studio
Name < / div >
< div


class ="qr-placeholder" >[GCash QR Code Here] < / div >

< p
style = "font-size: 0.9em; color: #555;" > Amount
to
pay: < strong >₱ < span
id = "pay_dp_amount" > < / span > < / strong > < / p >
< / div >

< form
id = "uploadForm"
enctype = "multipart/form-data"
style = "margin-top: 15px;" >
< input
type = "hidden"
id = "current_booking_id" >
< div


class ="form-group" >

< label > Upload
Payment
Receipt / Proof: < / label >
< input
type = "file"
id = "receipt"
accept = "image/png, image/jpeg, image/jpg"
required >
< / div >
< button
type = "submit" > Submit
Receipt & Complete
Booking < / button >
< / form >
< / div >
< / div >

< script >
const
packageRates = {"Solo": 249, "Duo": 399, "Squad": 599, "Party": 999};

function
calculateTotal()
{
    const
pkg = document.getElementById("package").value;
const
total = packageRates[pkg] | | 0;
const
dp = total * 0.5;
document.getElementById("dp_amount").innerText = dp.toFixed(2);
}

async function
fetchSlots()
{
    const
dateVal = document.getElementById("date").value;
const
schedSelect = document.getElementById("schedule");
schedSelect.innerHTML = '<option value="">Loading slots...</option>';

const
response = await fetch('/get-slots', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({date: dateVal})
});

const
data = await response.json();
schedSelect.innerHTML = '';

if (data.status === 'closed')
{
    schedSelect.innerHTML = ` < option
value = "" >${data.message} < / option > `;
return;
}

data.slots.forEach(slot= > {
    const
opt = document.createElement("option");
opt.value = slot.time;
opt.innerText = `${slot.time} ${slot.reason}
`;
if (slot.disabled)
opt.disabled = true;
schedSelect.appendChild(opt);
});
}

document.getElementById("bookingForm").addEventListener("submit", async (e) = > {
e.preventDefault();

const
pkg = document.getElementById("package").value;
const
grandTotal = packageRates[pkg];
const
downpayment = grandTotal * 0.5;

const
payload = {
    date: document.getElementById("date").value,
    schedule: document.getElementById("schedule").value,
    customer_name: document.getElementById("customer_name").value,
    contact_no: document.getElementById("contact_no").value,
    package: pkg,
    package_type: document.getElementById("package_type").value,
    is_student: 0,
    extra_pax: 0,
    extra_pet: 0,
    digital_copies: 0,
    extra_time: "None",
    extra_backdrop: 0,
    balloons: 0,
    grand_total: grandTotal,
    downpayment: downpayment,
    balance: grandTotal - downpayment
};

const
res = await fetch('/save-booking', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
});

const
result = await res.json();
if (result.success) {
document.getElementById("current_booking_id").value = result.booking_id;
document.getElementById("pay_dp_amount").innerText = downpayment.toFixed(2);
document.getElementById("bookingForm").classList.add("hidden");
document.getElementById("paymentSection").classList.remove("hidden");
} else {
alert("Error: " + result.message);
}
});

document.getElementById("uploadForm").addEventListener("submit", async (e) = > {
e.preventDefault();
const
formData = new
FormData();
formData.append("booking_id", document.getElementById("current_booking_id").value);
formData.append("receipt", document.getElementById("receipt").files[0]);

const
res = await fetch('/upload-receipt', {
    method: 'POST',
    body: formData
});

const
result = await res.json();
alert(result.message);
if (result.success) {
location.reload();
}
});
< / script >

    < / body >
        < / html >