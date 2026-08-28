"use strict";

function errorText(error) {
  return [
    error && error.message,
    error && error.childOutput,
    error && error.stack,
  ].filter(Boolean).join("\n");
}

function firstMatchingLine(text, pattern) {
  for (const line of String(text || "").split(/\r?\n/)) {
    if (pattern.test(line)) return line.trim();
  }
  return null;
}

function classifyBlockingError(error) {
  const message = error && error.message ? error.message : String(error || "неизвестная ошибка");
  const text = errorText(error);

  if (/passport\.yandex|sso\.dzen\.ru|oauth\.yandex|URL авторизации|ОШИБКА АВТОРИЗАЦИИ/i.test(text)) {
    const detail = firstMatchingLine(
      text,
      /Дзен перенаправил на URL авторизации|passport\.yandex|sso\.dzen\.ru|oauth\.yandex/i
    );
    return `ОШИБКА АВТОРИЗАЦИИ: ${detail || message}`;
  }

  if (/Порт \d+ уже занят|уже запущен.*Яндекс\.Браузер|Яндекс\.Браузер.*уже запущен/i.test(text)) {
    return (
      "ОШИБКА БРАУЗЕРА: роботизированный Яндекс.Браузер уже запущен либо " +
      `CDP-порт занят другим процессом. ${message}`
    );
  }

  if (
    /Яндекс\.Браузер не найден|browserProfile|CDP-порт|connectOverCDP|Не удалось подключиться к браузеру|основной контекст Яндекс\.Браузера/i.test(text)
  ) {
    return `ОШИБКА БРАУЗЕРА: ${message}`;
  }

  if (/config\.json|dzenUpload\.|browserDebug|timeZone|regularLog|errorLog/i.test(text)) {
    return `ОШИБКА КОНФИГУРАЦИИ: ${message}`;
  }

  if (/Не найден локальный MP4|PNG-обложка|ffmpeg|downloadedFile/i.test(text)) {
    return `ОШИБКА ЛОКАЛЬНЫХ ФАЙЛОВ: ${message}`;
  }

  if (/не завершился за операторское окно|тайм-аут|timeout/i.test(text)) {
    return `ОШИБКА ТАЙМ-АУТА: ${message}`;
  }

  return `ОШИБКА DZEN FLOW: ${message}`;
}

module.exports = {
  classifyBlockingError,
  errorText,
};
