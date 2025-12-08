/**
 * Encryption utilities for sensitive data
 * Uses AES-256-GCM encryption with Web Crypto API
 */

const ENCRYPTION_KEY_ENV = 'ENCRYPTION_KEY';

/**
 * Get or generate encryption key from environment
 * Key can be either:
 * 1. A base64-encoded 256-bit key
 * 2. A plain string (will be hashed to create a 256-bit key)
 */
async function getEncryptionKey(): Promise<CryptoKey> {
  const keyString = Deno.env.get(ENCRYPTION_KEY_ENV);
  
  if (!keyString) {
    throw new Error('ENCRYPTION_KEY not configured in environment');
  }

  let keyData: Uint8Array;

  // Try to decode as base64 first
  try {
    // Check if it's valid base64 (only base64 chars)
    if (/^[A-Za-z0-9+/]+=*$/.test(keyString) && keyString.length >= 32) {
      keyData = Uint8Array.from(atob(keyString), c => c.charCodeAt(0));
      // Ensure we have exactly 32 bytes for AES-256
      if (keyData.length >= 32) {
        keyData = keyData.slice(0, 32);
      } else {
        throw new Error('Key too short');
      }
    } else {
      throw new Error('Not valid base64');
    }
  } catch {
    // If not valid base64, hash the key string to get 256 bits
    const encoder = new TextEncoder();
    const keyBytes = encoder.encode(keyString);
    const hashBuffer = await crypto.subtle.digest('SHA-256', keyBytes);
    keyData = new Uint8Array(hashBuffer);
  }
  
  return await crypto.subtle.importKey(
    'raw',
    keyData.buffer as ArrayBuffer,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt']
  );
}

/**
 * Encrypt sensitive data
 * Returns base64-encoded string: iv:ciphertext
 */
export async function encrypt(plaintext: string): Promise<string> {
  try {
    const key = await getEncryptionKey();
    
    // Generate random IV (12 bytes for GCM)
    const iv = crypto.getRandomValues(new Uint8Array(12));
    
    // Encrypt
    const encoder = new TextEncoder();
    const data = encoder.encode(plaintext);
    
    const ciphertext = await crypto.subtle.encrypt(
      { name: 'AES-GCM', iv },
      key,
      data
    );
    
    // Combine IV and ciphertext
    const combined = new Uint8Array(iv.length + ciphertext.byteLength);
    combined.set(iv, 0);
    combined.set(new Uint8Array(ciphertext), iv.length);
    
    // Return as base64
    return btoa(String.fromCharCode(...combined));
    
  } catch (error) {
    console.error('Encryption error:', error);
    throw new Error('Failed to encrypt data');
  }
}

/**
 * Decrypt sensitive data
 * Input format: base64-encoded string containing iv:ciphertext
 */
export async function decrypt(encrypted: string): Promise<string> {
  try {
    const key = await getEncryptionKey();
    
    // Decode base64
    const combined = Uint8Array.from(atob(encrypted), c => c.charCodeAt(0));
    
    // Extract IV (first 12 bytes)
    const iv = combined.slice(0, 12);
    const ciphertext = combined.slice(12);
    
    // Decrypt
    const decrypted = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv },
      key,
      ciphertext
    );
    
    const decoder = new TextDecoder();
    return decoder.decode(decrypted);
    
  } catch (error) {
    console.error('Decryption error:', error);
    throw new Error('Failed to decrypt data');
  }
}

/**
 * Generate a new encryption key (for initial setup)
 * Run this once and store in Supabase secrets
 */
export function generateEncryptionKey(): string {
  const key = crypto.getRandomValues(new Uint8Array(32)); // 256 bits
  return btoa(String.fromCharCode(...key));
}