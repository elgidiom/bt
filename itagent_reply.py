#!/usr/bin/env python3
"""itagent_reply — el agente local usa esto para escribirle al usuario por Google Chat.

Uso:
  python3 itagent_reply.py '<space>' '<mensaje>' ['<thread>']

Ejemplo:
  python3 /home/gidiom/.it-board/itagent_reply.py 'spaces/AAQA2WfeUQk' 'Ya terminé ✅' 'spaces/AAQA2WfeUQk/threads/oBXJfGX8aPU'
"""
import sys
import itagent_common as ic

def main():
    if len(sys.argv) < 3:
        print("uso: itagent_reply.py '<space>' '<mensaje>' ['<thread>']", file=sys.stderr)
        sys.exit(2)
    space = sys.argv[1]
    text = sys.argv[2]
    thread = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] else None
    res = ic.post_message(space, text, thread)
    print("sent:", res.get("name", "ok"))

if __name__ == "__main__":
    main()
