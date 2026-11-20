from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()
DUMMY_HASH = password_hash.hash("not-a-real-password")
