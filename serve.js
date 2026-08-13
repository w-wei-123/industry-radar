// 静态服务器 - 中文用户名兼容版
const http = require('http');
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, 'docs');
const PORT = 9002;

const MIME = {
  '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css',
  '.json': 'application/json', '.txt': 'text/plain', '.png': 'image/png',
  '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.ico': 'image/x-icon',
  '.woff2': 'font/woff2', '.woff': 'font/woff',
};

http.createServer((req, res) => {
  let urlPath = decodeURIComponent(req.url.split('?')[0]);
  if (urlPath === '/') urlPath = '/index.html';
  // 去掉末尾斜杠（Next.js export 是 xxx.html 文件 + 同名目录共存）
  if (urlPath.endsWith('/')) urlPath = urlPath.slice(0, -1);

  let filePath = path.join(ROOT, urlPath);
  // 解析顺序：.html 文件优先（Next.js export 为 xxx.html + 同名目录共存）> 精确文件 > 目录/index.html
  const htmlAlt = filePath + '.html';
  if (fs.existsSync(htmlAlt)) {
    filePath = htmlAlt;
  } else if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
    filePath = path.join(filePath, 'index.html');
  }
  if (!fs.existsSync(filePath)) {
    res.writeHead(404); res.end('404 Not Found: ' + urlPath);
    return;
  }
  const ext = path.extname(filePath).toLowerCase();
  res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' });
  fs.createReadStream(filePath).pipe(res);
}).listen(PORT, '127.0.0.1', () => {
  console.log('Server running at http://127.0.0.1:' + PORT);
});
