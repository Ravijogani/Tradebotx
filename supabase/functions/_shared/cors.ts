// Shared CORS headers for edge functions. Previously every function
// redefined an identical wildcard-origin block locally (34 copies) — not
// exploitable on its own since every function authenticates via a bearer
// token rather than cookies, but it meant any future origin-restriction
// change required touching every file individually instead of one place.

export const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

// get-approved-users is called by the external bot manager with a custom
// header instead of a Supabase client, so it needs x-custom-auth allowed too.
export const corsHeadersWithCustomAuth = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type, x-custom-auth",
};
