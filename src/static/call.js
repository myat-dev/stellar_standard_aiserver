const frame = document.getElementById('call-frame');
const callButton = document.getElementById('call-button');
const statusText = document.getElementById('status-text');

let timerInterval;
let seconds = 0;
let device;
let token;
let params;
let currentCall = null;

function startCallTimer() {
  timerInterval = setInterval(() => {
    seconds++;
    const min = String(Math.floor(seconds / 60)).padStart(2, '0');
    const sec = String(seconds % 60).padStart(2, '0');
    statusText.textContent = `${min}:${sec}`;
  }, 1000);
}

async function makeCall() {
    await startupClient();
    updateUIForCallInProgress();
    await makeOutgoingCall();
}

async function startupClient() {
    console.log("Requesting Access Token...");

    try {
      const data = await $.getJSON("/token");
      console.log("Got a token.");
      token = data.token; 
      await loadPhoneNumber();
      initializeDevice();
    } catch (err) {
      console.log(err);
      console.log("An error occurred. See your browser console for more information.");
    }
}


async function loadPhoneNumber(){
    try {
        const response = await fetch("static/config.yaml");
        const yamlText = await response.text();
        const config = jsyaml.load(yamlText);

        if (config.callMode === "phone") {
            const phoneNumber = config.phoneNumber;
            console.log("Calling real phone number:", phoneNumber);
            params = { To: phoneNumber }; // ✅ Real phone number
        } else if (config.callMode === "client") {
            const clientName = config.clientName;
            console.log("Calling client:", clientName);
            params = { To: `client:${clientName}` };
        } else {
            console.error("Invalid callMode in config.yaml (use 'phone' or 'client')");
        }
    } catch (error) {
        console.error("Failed to load phone number from config.yaml:", error);
    }
}


function initializeDevice() {
    device = new Twilio.Device(token, {
      logLevel: 1,
      // Set Opus as our preferred codec. Opus generally performs better, requiring less bandwidth and
      // providing better audio quality in restrained network conditions.
      codecPreferences: ["opus", "pcmu"]
    });
    addDeviceListeners(device);
    device.register();
}

function addDeviceListeners(device) {
    device.on("registered", function () {
      console.log("Twilio.Device Ready to make and receive calls!");
    });

    device.on("error", function (error) {
      console.log("Twilio.Device Error: " + error.message);
    });
}

async function makeOutgoingCall() {
    
    if (device){
        console.log(`Attempting to call ...`);
        console.log("Params being passed to connect:", params);
        currentCall = await device.connect({params});

        currentCall.on("accept", updateUICallAccepted);
        currentCall.on("disconnect", updateUIForEndedCall);
        currentCall.on("cancel", updateUICallReady);
    }
    else{
        console.log("Unable to make call, device not initialized.");
    }
}

function switchToActiveCall() {
  statusText.textContent = '00:00';
  startCallTimer();
}

function endCall() {
  if (currentCall) {
    console.log("Ending call...");
    currentCall.disconnect();
    currentCall = null;
  }
  updateUIForEndedCall();
}


// UI update functions
function updateUICallReady(){
  clearInterval(timerInterval);
  seconds = 0;
  statusText.textContent = '';
  callButton.classList.remove('bg-red-500', 'hover:bg-red-600');
  callButton.classList.add('bg-green-500', 'hover:bg-green-600');
  callButton.innerHTML = `
    <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
      <path d="M6.62 10.79a15.053 15.053 0 006.59 6.59l2.2-2.2a1 1 0 011.11-.27c1.2.48 2.53.73 3.88.73a1 1 0 011 1V20a1 1 0 01-1 1C10.4 21 3 13.6 3 5a1 1 0 011-1h3.5a1 1 0 011 1c0 1.35.25 2.68.73 3.88.13.28.07.6-.27 1.11l-2.34 2.34z"/>
    </svg>
  `;
}

function updateUICallAccepted() {
  statusText.textContent = '00:00';
  startCallTimer();
}

function updateUIForCallInProgress() {
  callButton.classList.remove('bg-green-500', 'hover:bg-green-600');
  callButton.classList.add('bg-red-500', 'hover:bg-red-600');
  callButton.innerHTML = `
    <svg class="w-6 h-6 [transform:rotate(140deg)]" fill="currentColor" viewBox="0 0 24 24">
        <path d="M6.62 10.79a15.053 15.053 0 006.59 6.59l2.2-2.2a1 1 0 011.11-.27c1.2.48 2.53.73 3.88.73a1 1 0 011 1V20a1 1 0 01-1 1C10.4 21 3 13.6 3 5a1 1 0 011-1h3.5a1 1 0 011 1c0 1.35.25 2.68.73 3.88.13.28.07.6-.27 1.11l-2.34 2.34z"/>
    </svg>
  `;
  statusText.textContent = '接続中...';
}

function updateUIForEndedCall()
{
  clearInterval(timerInterval);
  seconds = 0;
  statusText.textContent = '';
  callButton.classList.remove('bg-red-500', 'hover:bg-red-600');
  callButton.classList.add('bg-green-500', 'hover:bg-green-600');
  callButton.innerHTML = `
    <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
      <path d="M6.62 10.79a15.053 15.053 0 006.59 6.59l2.2-2.2a1 1 0 011.11-.27c1.2.48 2.53.73 3.88.73a1 1 0 011 1V20a1 1 0 01-1 1C10.4 21 3 13.6 3 5a1 1 0 011-1h3.5a1 1 0 011 1c0 1.35.25 2.68.73 3.88.13.28.07.6-.27 1.11l-2.34 2.34z"/>
    </svg>
  `;
}
// Event listeners

callButton.addEventListener('click', () => {
  if (callButton.classList.contains('bg-green-500')) {
    makeCall();
  } else {
    endCall();
  }
});
