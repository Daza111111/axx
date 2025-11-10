/*
  # Fix RLS policies for users table
  
  1. Changes
    - Add INSERT policy to allow user registration (public access)
    - Keep existing SELECT and UPDATE policies for authenticated users
  
  2. Security
    - Allow anyone to create user accounts (needed for registration)
    - Only authenticated users can read their own data
    - Only authenticated users can update their own data
*/

-- Drop existing policies if they exist to recreate them
DROP POLICY IF EXISTS "Users can read own data" ON users;
DROP POLICY IF EXISTS "Users can update own data" ON users;
DROP POLICY IF EXISTS "Anyone can register" ON users;
DROP POLICY IF EXISTS "Public can create users" ON users;

-- Allow public registration (INSERT without authentication)
CREATE POLICY "Public can create users"
  ON users
  FOR INSERT
  TO anon, authenticated
  WITH CHECK (true);

-- Authenticated users can read their own data
CREATE POLICY "Users can read own data"
  ON users
  FOR SELECT
  TO authenticated
  USING (auth.uid()::text = id::text);

-- Authenticated users can update their own data
CREATE POLICY "Users can update own data"
  ON users
  FOR UPDATE
  TO authenticated
  USING (auth.uid()::text = id::text)
  WITH CHECK (auth.uid()::text = id::text);
