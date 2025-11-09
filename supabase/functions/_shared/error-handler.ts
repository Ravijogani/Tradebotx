// Secure error handling utility for edge functions
// Returns generic error messages to users while logging details server-side

export interface ErrorResponse {
  error: string;
  error_id?: string;
}

export function generateErrorId(): string {
  return `ERR-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

export function getErrorCategory(error: any): string {
  const message = error?.message?.toLowerCase() || '';
  
  if (message.includes('auth') || message.includes('unauthorized') || message.includes('not authenticated')) {
    return 'auth';
  }
  if (message.includes('not found') || message.includes('does not exist')) {
    return 'not_found';
  }
  if (message.includes('validation') || message.includes('invalid') || message.includes('required')) {
    return 'validation';
  }
  if (message.includes('rate limit') || message.includes('too many')) {
    return 'rate_limit';
  }
  if (message.includes('payment') || message.includes('subscription')) {
    return 'payment';
  }
  return 'internal';
}

export function getGenericErrorMessage(error: any): string {
  const category = getErrorCategory(error);
  
  const messages: Record<string, string> = {
    auth: 'Authentication failed. Please log in and try again.',
    not_found: 'The requested resource was not found.',
    validation: 'Invalid input provided. Please check your data and try again.',
    rate_limit: 'Too many requests. Please try again later.',
    payment: 'Payment processing failed. Please try again or contact support.',
    internal: 'An error occurred processing your request. Please try again later.'
  };
  
  return messages[category] || messages.internal;
}

export function handleError(error: any, corsHeaders: Record<string, string>): Response {
  // Log full error details server-side
  const errorId = generateErrorId();
  console.error(`[${errorId}] Error details:`, {
    message: error.message,
    stack: error.stack,
    name: error.name,
    timestamp: new Date().toISOString()
  });
  
  // Return generic message to client
  const genericMessage = getGenericErrorMessage(error);
  
  return new Response(
    JSON.stringify({
      error: genericMessage,
      error_id: errorId
    }),
    {
      status: error.status || 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    }
  );
}
