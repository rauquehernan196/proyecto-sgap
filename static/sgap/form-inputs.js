function formatDateTime(value) {
  const digits = value.replace(/\D/g, "").slice(0, 12);
  let formatted = digits.slice(0, 2);

  if (digits.length > 2) {
    formatted += `/${digits.slice(2, 4)}`;
  }
  if (digits.length > 4) {
    formatted += `/${digits.slice(4, 8)}`;
  }
  if (digits.length > 8) {
    formatted += ` ${digits.slice(8, 10)}`;
  }
  if (digits.length > 10) {
    formatted += `:${digits.slice(10, 12)}`;
  }
  return formatted;
}

document.querySelectorAll("[data-datetime-mask]").forEach((input) => {
  input.addEventListener("input", () => {
    const digitsBeforeCaret = input.value
      .slice(0, input.selectionStart)
      .replace(/\D/g, "").length;
    const formatted = formatDateTime(input.value);
    input.value = formatted;

    let cursor = 0;
    let digitsSeen = 0;
    while (cursor < formatted.length && digitsSeen < digitsBeforeCaret) {
      if (/\d/.test(formatted[cursor])) {
        digitsSeen += 1;
      }
      cursor += 1;
    }
    input.setSelectionRange(cursor, cursor);
  });
});
