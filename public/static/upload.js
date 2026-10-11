// Загрузка фото/аудио прямо из браузера в хранилище (минуя сервер).
// Разметка: <div class="uploader" data-kind="image|audio"> <input type=file> <input type=hidden name="image_path"> <div class="up-status"></div> </div>
(function () {
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  const MAX_SIDE = 2000;          // фото больше этого по длинной стороне уменьшаем
  const JPEG_QUALITY = 0.85;
  let pending = 0;

  function setStatus(box, text, cls) {
    const el = box.querySelector(".up-status");
    el.textContent = text;
    el.className = "up-status " + (cls || "");
  }

  function lockForms(lock) {
    document.querySelectorAll("form button:not(.danger)").forEach(b => (b.disabled = lock));
  }

  // Сжимаем jpg/png/webp через canvas. Если не вышло (HEIC и т.п.) — грузим как есть.
  async function maybeCompress(file) {
    if (!/^image\/(jpeg|png|webp)$/.test(file.type)) return file;
    try {
      const bmp = await createImageBitmap(file);
      const scale = Math.min(1, MAX_SIDE / Math.max(bmp.width, bmp.height));
      if (scale === 1 && file.size < 1.5 * 1024 * 1024) return file;
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(bmp.width * scale);
      canvas.height = Math.round(bmp.height * scale);
      canvas.getContext("2d").drawImage(bmp, 0, 0, canvas.width, canvas.height);
      const blob = await new Promise(r => canvas.toBlob(r, "image/jpeg", JPEG_QUALITY));
      if (!blob || blob.size >= file.size) return file;
      return new File([blob], file.name.replace(/\.\w+$/, "") + ".jpg", { type: "image/jpeg" });
    } catch { return file; }
  }

  async function upload(box, input) {
    const original = input.files[0];
    if (!original) return;
    const hidden = box.querySelector('input[type="hidden"]');
    pending++; lockForms(true);
    try {
      setStatus(box, "Готовлю файл…");
      const file = box.dataset.kind === "image" ? await maybeCompress(original) : original;

      setStatus(box, "Получаю ссылку…");
      const r = await fetch("/admin/upload-url", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: JSON.stringify({ kind: box.dataset.kind, filename: file.name, content_type: file.type }),
      });
      const t = await r.json();
      if (!r.ok) throw new Error(t.error || r.status);

      setStatus(box, `Загружаю ${(file.size / 1024 / 1024).toFixed(1)} МБ…`);
      const up = await fetch(t.url, { method: t.method, headers: t.headers, body: file });
      if (!up.ok) throw new Error("хранилище ответило " + up.status + " " + (await up.text()).slice(0, 120));

      hidden.value = t.path;
      setStatus(box, "✅ Загружено — не забудь нажать «Сохранить»", "ok");
      const prev = box.querySelector(".up-preview");
      if (prev) prev.remove();
      const el = document.createElement(box.dataset.kind === "image" ? "img" : "audio");
      el.className = "up-preview " + (box.dataset.kind === "image" ? "photo" : "");
      el.src = URL.createObjectURL(file);
      if (el.tagName === "AUDIO") el.controls = true;
      else el.style.cssText = "max-height:200px;object-fit:cover";
      box.appendChild(el);
    } catch (e) {
      hidden.value = "";
      input.value = "";
      setStatus(box, "❌ Не загрузилось: " + e.message, "bad");
    } finally {
      pending--; if (!pending) lockForms(false);
    }
  }

  document.querySelectorAll(".uploader").forEach(box => {
    const input = box.querySelector('input[type="file"]');
    input.addEventListener("change", () => upload(box, input));
  });

  document.querySelectorAll("form").forEach(f => f.addEventListener("submit", e => {
    if (pending) { e.preventDefault(); alert("Подожди, файл ещё загружается"); }
  }));
})();
