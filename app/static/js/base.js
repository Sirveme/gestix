async function pedirSustento(modulo, id, codigo, descripcion, monto, fecha) {
    const motivo = prompt(`Por que solicitas sustento?\n${descripcion}`);
    if (!motivo) return;

    const resp = await fetch('/inventario/sustento/agregar-item', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            modulo, id_operacion: id,
            codigo_operacion: codigo,
            descripcion, monto, fecha,
            motivo_consulta: motivo,
        }),
    });
    const result = await resp.json();
    if (result.ok) {
        const toast = document.createElement('div');
        toast.className = 'toast toast-ok';
        toast.textContent = result.mensaje;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    }
}
