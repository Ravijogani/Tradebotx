-- Helper function to create admin user
-- This is a one-time setup function
CREATE OR REPLACE FUNCTION create_admin_account(
  admin_email TEXT,
  admin_password TEXT,
  admin_name TEXT DEFAULT 'Admin'
)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  new_user_id uuid;
  result json;
BEGIN
  -- Create the user in auth.users (this is normally done by Supabase Auth)
  -- Note: This function should only be used in development/initial setup
  -- For production, create users through the normal signup flow and then promote them
  
  -- Check if user already exists
  SELECT id INTO new_user_id FROM auth.users WHERE email = admin_email;
  
  IF new_user_id IS NOT NULL THEN
    -- User exists, just add admin role if not already admin
    IF NOT EXISTS (SELECT 1 FROM user_roles WHERE user_id = new_user_id AND role = 'admin') THEN
      INSERT INTO user_roles (user_id, role)
      VALUES (new_user_id, 'admin');
      
      result := json_build_object(
        'success', true,
        'message', 'Admin role added to existing user',
        'user_id', new_user_id,
        'email', admin_email
      );
    ELSE
      result := json_build_object(
        'success', true,
        'message', 'User is already an admin',
        'user_id', new_user_id,
        'email', admin_email
      );
    END IF;
  ELSE
    -- Return instructions for creating the user
    result := json_build_object(
      'success', false,
      'message', 'User does not exist. Please create account through signup first, then run this function again to promote to admin.',
      'email', admin_email
    );
  END IF;
  
  RETURN result;
END;
$$;

-- Grant execute permission to authenticated users
GRANT EXECUTE ON FUNCTION create_admin_account TO authenticated;

COMMENT ON FUNCTION create_admin_account IS 'Helper function to promote existing users to admin role. User must be created through normal signup flow first.';