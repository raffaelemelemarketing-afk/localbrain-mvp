// GDPR Cookie Banner for LocalBrain
(function() {
    'use strict';

    // Cookie functions
    function setCookie(name, value, days) {
        const expires = new Date();
        expires.setTime(expires.getTime() + (days * 24 * 60 * 60 * 1000));
        document.cookie = name + '=' + value + ';expires=' + expires.toUTCString() + ';path=/;SameSite=Lax';
    }

    function getCookie(name) {
        const nameEQ = name + '=';
        const ca = document.cookie.split(';');
        for (let i = 0; i < ca.length; i++) {
            let c = ca[i];
            while (c.charAt(0) === ' ') c = c.substring(1, c.length);
            if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
        }
        return null;
    }

    function deleteCookie(name) {
        document.cookie = name + '=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/;SameSite=Lax';
    }

    // Cookie banner functionality
    function createCookieBanner() {
        // Check if user has already made a choice
        const cookieConsent = getCookie('localbrain_cookie_consent');

        if (cookieConsent) {
            return; // User already made a choice
        }

        // Create banner HTML
        const bannerHTML = `
            <div id="cookie-banner" style="
                position: fixed;
                bottom: 0;
                left: 0;
                right: 0;
                background: #1c3faa;
                color: white;
                padding: 1.5rem 2rem;
                z-index: 1000;
                box-shadow: 0 -4px 12px rgba(0,0,0,0.1);
                font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            ">
                <div style="max-width: 1200px; margin: 0 auto; display: flex; flex-wrap: wrap; gap: 1rem; align-items: center; justify-content: space-between;">
                    <div style="flex: 1; min-width: 300px;">
                        <h3 style="margin: 0 0 0.5rem 0; font-size: 1.1rem;">🍪 Gestione dei Cookie</h3>
                        <p style="margin: 0; font-size: 0.9rem; line-height: 1.4;">
                            Utilizziamo cookie tecnici necessari per il funzionamento del sito.
                            Per maggiori informazioni, consulta la nostra
                            <a href="/privacy-policy" style="color: #93c5fd; text-decoration: underline;">Privacy Policy</a>.
                        </p>
                    </div>
                    <div style="display: flex; gap: 0.75rem; flex-wrap: wrap;">
                        <button id="cookie-accept-necessary" style="
                            padding: 0.6rem 1.2rem;
                            background: #374151;
                            color: white;
                            border: none;
                            border-radius: 8px;
                            cursor: pointer;
                            font-weight: 600;
                            font-size: 0.9rem;
                        ">Accetta Necessari</button>
                        <button id="cookie-accept-all" style="
                            padding: 0.6rem 1.2rem;
                            background: #10b981;
                            color: white;
                            border: none;
                            border-radius: 8px;
                            cursor: pointer;
                            font-weight: 600;
                            font-size: 0.9rem;
                        ">Accetta Tutti</button>
                    </div>
                </div>
            </div>
        `;

        // Add banner to page
        document.body.insertAdjacentHTML('beforeend', bannerHTML);

        // Add event listeners
        document.getElementById('cookie-accept-necessary').addEventListener('click', function() {
            setCookie('localbrain_cookie_consent', 'necessary', 365);
            hideBanner();
        });

        document.getElementById('cookie-accept-all').addEventListener('click', function() {
            setCookie('localbrain_cookie_consent', 'all', 365);
            // Here you would also set analytics/functional cookies
            hideBanner();
        });
    }

    function hideBanner() {
        const banner = document.getElementById('cookie-banner');
        if (banner) {
            banner.style.display = 'none';
        }
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', createCookieBanner);
    } else {
        createCookieBanner();
    }

    // Export functions for external use if needed
    window.LocalBrainCookies = {
        setCookie: setCookie,
        getCookie: getCookie,
        deleteCookie: deleteCookie,
        acceptNecessary: function() {
            setCookie('localbrain_cookie_consent', 'necessary', 365);
            hideBanner();
        },
        acceptAll: function() {
            setCookie('localbrain_cookie_consent', 'all', 365);
            hideBanner();
        }
    };
})();