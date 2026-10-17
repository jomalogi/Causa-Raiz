import sys
import os
from pathlib import Path
import db

def main():
    if len(sys.argv) > 1:
        excel_path = sys.argv[1]
    else:
        excel_path = Path(__file__).resolve().parent / "Visitas_Calidad.xlsx"
        if not excel_path.exists():
            alt = Path("D:/IM/hallazgos/Visitas_Calidad.xlsx")
            if alt.exists():
                excel_path = alt

    if not Path(excel_path).exists():
        print(f"Error: No se encontró el archivo Excel en {excel_path}")
        sys.exit(1)

    print("=" * 60)
    print(f"Iniciando cargue diario de visitas: {excel_path}")
    print("=" * 60)

    db.init_db()
    cargue_id, total = db.cargar_visitas_excel(str(excel_path), usuario=os.getenv("USER", "CLI"))
    print(f"¡Cargue finalizado con éxito!")
    print(f"Lote ID asignado: {cargue_id}")
    print(f"Total registros cargados: {total}")
    print("=" * 60)

if __name__ == "__main__":
    main()
