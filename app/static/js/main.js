async function cargarFamilias() {
    const mensajeDiv = document.getElementById('mensaje');
    mensajeDiv.textContent = "Cargando familias...";
    mensajeDiv.style.display = 'block';
    mensajeDiv.style.backgroundColor = '#fff3cd';
    mensajeDiv.style.color = '#856404';
    mensajeDiv.style.border = '1px solid #ffeeba';

    try {
        const res = await fetch('/familias');
        const data = await res.json();

        if (data.length === 0) {
            // Reintenta una vez después de una pequeña espera
            setTimeout(cargarFamilias, 500);  // espera 0.5 segundos
        } else {
            familias = data;
            mostrarFamilias(familias);
            mensajeDiv.style.display = 'none';
        }
    } catch (err) {
        console.error("❌ Error al cargar familias:", err);
        mensajeDiv.textContent = "No se pudieron cargar las familias";
        mensajeDiv.style.backgroundColor = '#f8d7da';
        mensajeDiv.style.color = '#721c24';
        mensajeDiv.style.border = '1px solid #f5c6cb';
    }
}


document.addEventListener('DOMContentLoaded', () => {
    cargarFamilias();
});
