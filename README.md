# Peper.io 2 (Socket.io + Flutter) starter

This repository contains a minimal multiplayer starter for a peper.io-style game.

## Structure
- `server/`: Node.js + Socket.io authoritative server loop
- `client/`: Flutter client using `socket_io_client`

## Run server
```bash
cd server
npm install
npm run dev
```

## Run Flutter client
```bash
cd client
flutter pub get
flutter run
```

Update the server URL in `client/lib/main.dart` if you are running on a device/emulator.
