import http from 'http';
import express from 'express';
import { Server } from 'socket.io';

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
  cors: { origin: '*' }
});

const TICK_RATE_MS = 50;
const WORLD_SIZE = 2000;

const players = new Map();

function createPlayer(id, name) {
  return {
    id,
    name,
    x: Math.random() * WORLD_SIZE,
    y: Math.random() * WORLD_SIZE,
    vx: 0,
    vy: 0,
    score: 0
  };
}

io.on('connection', (socket) => {
  socket.on('join', ({ name }) => {
    const player = createPlayer(socket.id, name || 'Player');
    players.set(socket.id, player);
    socket.emit('world:init', {
      id: socket.id,
      worldSize: WORLD_SIZE,
      players: Array.from(players.values())
    });
    socket.broadcast.emit('player:joined', player);
  });

  socket.on('input', ({ vx, vy }) => {
    const player = players.get(socket.id);
    if (!player) return;
    player.vx = Math.max(-1, Math.min(1, vx));
    player.vy = Math.max(-1, Math.min(1, vy));
  });

  socket.on('disconnect', () => {
    const player = players.get(socket.id);
    if (!player) return;
    players.delete(socket.id);
    socket.broadcast.emit('player:left', { id: socket.id });
  });
});

setInterval(() => {
  for (const player of players.values()) {
    player.x = Math.max(0, Math.min(WORLD_SIZE, player.x + player.vx * 6));
    player.y = Math.max(0, Math.min(WORLD_SIZE, player.y + player.vy * 6));
  }
  io.emit('world:state', Array.from(players.values()));
}, TICK_RATE_MS);

app.get('/', (_req, res) => {
  res.json({ status: 'ok', players: players.size });
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(`Server running on :${PORT}`);
});
