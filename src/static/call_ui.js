// call_ui.js
window.addEventListener("load", () => {
  let nameValue = "";
  let phoneValue = "";

  if (window.location.hash) {
    const hashParams = new URLSearchParams(window.location.hash.slice(1));
    nameValue = hashParams.get("name");
    phoneValue = hashParams.get("phone");
  } else {
    const urlParams = new URLSearchParams(window.location.search);
    nameValue = urlParams.get("name");
    phoneValue = urlParams.get("phone");
  }

  if (phoneValue) {
    phoneValue = phoneValue.replace(/\s/g, "+");
  }

  const agentName = nameValue || "担当者";
  let formattedPhone = phoneValue ? phoneValue.trim() : "";


  if (!formattedPhone.startsWith("+")) {
    // Remove any leading zero (Japan domestic numbers often start with 0)
    if (formattedPhone.startsWith("0")) {
      formattedPhone = formattedPhone.substring(1);
    }
    formattedPhone = "+81" + formattedPhone;
  }

  const agentLabel = document.getElementById("agent-name");
  if (agentLabel) agentLabel.textContent = agentName;

  window.selectedPhoneNumber = formattedPhone;
  console.log("Selected phone (from URL):", window.selectedPhoneNumber);

});
