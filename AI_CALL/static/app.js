const callBtn = document.getElementById('callBtn')
const status = document.getElementById('status')
const phoneInput = document.getElementById('phone')
const connecting = document.getElementById('connecting')

function setConnecting(on){
  connecting.style.visibility = on ? 'visible' : 'hidden'
  status.textContent = on ? 'Connecting...' : 'Idle'
}

callBtn.addEventListener('click', async ()=>{
  const phone = phoneInput.value.trim()
  if(!phone){
    status.textContent = 'Enter a phone number'
    return
  }

  setConnecting(true)

  try{
    const resp = await fetch('/trigger_call',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({phone})
    })
    const data = await resp.json()
    if(resp.ok){
      status.textContent = data.status === 'simulated' ? 'Simulated' : 'Call started'
    } else {
      status.textContent = data.error || 'Error'
    }
  }catch(err){
    status.textContent = err.message || 'Network error'
  }finally{
    setTimeout(()=>setConnecting(false), 1200)
  }
})
