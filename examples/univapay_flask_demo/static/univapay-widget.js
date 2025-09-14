/**
 * Local UniVapay Widget for Demo Purposes
 * This provides the window.UniVapay.open() interface that the Flask demo expects
 */
(function (global) {
  'use strict';
  
  console.log('[LocalWidget] Script loading...');

  // Create a mock payment modal
  function createPaymentModal(config) {
    var modal = document.createElement('div');
    modal.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0,0,0,0.8);
      z-index: 10000;
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: system-ui, -apple-system, sans-serif;
    `;
    
    var content = document.createElement('div');
    content.style.cssText = `
      background: white;
      border-radius: 12px;
      padding: 24px;
      max-width: 400px;
      width: 90%;
      text-align: center;
      box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
    `;
    
    var widget = config.widgets ? Object.values(config.widgets)[0] : {};
    var amount = widget.amount || 0;
    var description = widget.description || 'Payment';
    
    content.innerHTML = `
      <h3 style="margin: 0 0 16px 0; color: #1f2937;">UniVapay Payment</h3>
      <p style="margin: 0 0 16px 0; color: #6b7280;">${description}</p>
      <div style="font-size: 24px; font-weight: bold; margin: 16px 0; color: #059669;">
        Â¥${amount.toLocaleString()}
      </div>
      <div style="margin: 24px 0;">
        <button id="mock-pay-btn" style="
          background: #059669;
          color: white;
          border: none;
          padding: 12px 24px;
          border-radius: 8px;
          font-size: 16px;
          cursor: pointer;
          margin-right: 8px;
        ">Pay Now</button>
        <button id="mock-cancel-btn" style="
          background: #6b7280;
          color: white;
          border: none;
          padding: 12px 24px;
          border-radius: 8px;
          font-size: 16px;
          cursor: pointer;
        ">Cancel</button>
      </div>
      <div style="font-size: 12px; color: #9ca3af; margin-top: 16px;">
        Demo Mode - This is a mock payment interface
      </div>
    `;
    
    modal.appendChild(content);
    document.body.appendChild(modal);
    
    // Handle payment
    document.getElementById('mock-pay-btn').onclick = function() {
      // Simulate payment processing
      content.innerHTML = `
        <h3 style="margin: 0 0 16px 0; color: #1f2937;">Processing Payment...</h3>
        <div style="margin: 24px 0;">
          <div style="width: 40px; height: 40px; border: 4px solid #e5e7eb; border-top: 4px solid #059669; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto;"></div>
        </div>
        <style>
          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
        </style>
      `;
      
      // Simulate payment success after 2 seconds
      setTimeout(function() {
        document.body.removeChild(modal);
        
        // Trigger success event
        var event = new CustomEvent('univapay:success', {
          detail: {
            chargeId: 'mock_charge_' + Date.now(),
            tokenId: 'mock_token_' + Date.now(),
            resourceType: widget.checkout === 'payment' ? 'one_time' : 'subscription',
            amount: amount,
            currency: 'jpy'
          }
        });
        window.dispatchEvent(event);
      }, 2000);
    };
    
    // Handle cancel
    document.getElementById('mock-cancel-btn').onclick = function() {
      document.body.removeChild(modal);
      
      // Trigger close event
      var event = new CustomEvent('univapay:closed', {
        detail: {}
      });
      window.dispatchEvent(event);
    };
    
    // Handle clicking outside modal
    modal.onclick = function(e) {
      if (e.target === modal) {
        document.getElementById('mock-cancel-btn').click();
      }
    };
    
    // Trigger opened event
    var openedEvent = new CustomEvent('univapay:opened', {
      detail: {}
    });
    window.dispatchEvent(openedEvent);
  }

  // Create the UniVapay global object
  global.UniVapay = {
    open: function(envelope) {
      console.log('[LocalWidget] UniVapay.open called with:', envelope);
      createPaymentModal(envelope);
    }
  };

  console.log('[LocalWidget] Local UniVapay widget loaded');
  console.log('[LocalWidget] window.UniVapay available:', !!global.UniVapay);

})(typeof window !== "undefined" ? window : this);