/* Paradise.mx site configuration.
   The inbox address is stored encoded and only assembled in the browser at submit time. */
window.PARADISE_CONFIG = {
  site: "Paradise.mx",
  canonicalBase: "https://paradise.mx",
  adClient: "ca-pub-6620975821265271",
  /* Paste AdSense display-unit slot IDs here to enable in-content units (auto ads run without them). */
  adSlots: { inContent: "", sidebar: "" },
  /* Paste hosted payment links (Stripe Payment Links, PayPal hosted button page, Buy Me a Coffee, etc.)
     to switch donations from pledge-by-form to instant checkout. Leave empty to keep pledges. */
  pay: { oneTime: "", monthly: "", label: "" },
  _k: [[118, 126, 105, 108, 126], [110, 71, 56, 104, 122, 114, 121], [116, 118, 106, 53, 115, 112, 104, 116]],
  _s: 7
};
(function(c){
  c.inbox = function(){
    return c._k.map(function(p){ return p.map(function(n){ return String.fromCharCode(n - c._s); }).join("").split("").reverse().join(""); }).join("");
  };
  c.endpoint = function(){ return "https://formsubmit.co/ajax/" + c.inbox(); };
})(window.PARADISE_CONFIG);
