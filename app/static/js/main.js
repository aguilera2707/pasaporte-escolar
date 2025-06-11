async function consultarFamilia() {
    const id = document.getElementById('familiaId').value;

    if (!id) return alert("Ingresa un ID válido");

    // Obtener datos de la familia
    const resFamilia = await fetch(`/familia/${id}`);
    if (!resFamilia.ok) {
        alert("Familia no encontrada");
        return;
    }
    const familia = await resFamilia.json();

    // Mostrar info
    document.getElementById('nombreFamilia').innerText = familia.nombre;
    document.getElementById('puntosFamilia').innerText = familia.puntos;
    document.getElementById('infoFamilia').style.display = 'block';

    // Obtener historial de transacciones
    const resHistorial = await fetch(`/familia/${id}/transacciones`);
    const transacciones = await resHistorial.json();

    const lista = document.getElementById('listaTransacciones');
    lista.innerHTML = ''; // limpiar
    transacciones.forEach(tx => {
        const li = document.createElement('li');
        li.textContent = `${tx.fecha.split('T')[0]} - ${tx.tipo.toUpperCase()} - ${tx.puntos} pts - ${tx.descripcion}`;
        lista.appendChild(li);
    });
    document.getElementById('historial').style.display = 'block';
}