import streamlit as st
from google import genai
import pypdf
import time
from pptx import Presentation
import docx
import openpyxl 
import io 

# 1. Configuración sin el page_icon
st.set_page_config(
    page_title="Corrector EEBE", 
    layout="wide"
)

# 2. Estilos para los títulos (Azul oscuro en claro, Azul celeste en oscuro)
estilos_upc = """
<style>
    /* 1. Títulos en Modo Claro (Azul UPC) */
    h1, h2, h3 {
        color: #1363A2 !important;
    }

    /* 2. Títulos en Modo Oscuro (Azul Celeste para contraste) */
    @media (prefers-color-scheme: dark) {
        h1, h2, h3 {
            color: #63B3ED !important;
        }
    }

    /* 3. Colorear el botón de "Evaluar Trabajo" con el Azul UPC */
    div.stButton > button:first-child {
        background-color: #1363A2 !important;
        color: white !important;
        border: none !important;
    }
    
    /* Efecto al pasar el ratón por encima del botón */
    div.stButton > button:first-child:hover {
        background-color: #0e4b7a !important; 
    }
</style>
"""
st.markdown(estilos_upc, unsafe_allow_html=True)
st.title("Corrector Automático por Rúbricas")
st.write("Herramienta de apoyo para la evaluación de proyectos de ingeniería.")
st.caption("🔒 Aviso de Privacidad y Limitaciones: Los documentos subidos son procesados en memoria temporal y se eliminan al finalizar la evaluación. Se recomienda a los alumnos omitir datos personales sensibles. El sistema lee texto plano, no compila código fuente y podría omitir datos en anexos masivos. La calificación es una propuesta automática que requiere validación docente.")

api_key = st.text_input("Introduce tu API Key de Gemini:", type="password")

tono_evaluacion = st.selectbox(
    "¿Qué estilo de feedback quieres que genere la IA?",
    [
        "Constructivo (Recomendado: Notas detalladas y consejos de mejora)",
        "Estricto (Directo al grano, solo señala errores)",
        "Breve (Solo la nota final y una línea resumen por criterio)"
    ]
)

def extraer_texto_archivo(archivo):
    texto = ""
    nombre = archivo.name.lower()
    try:
        if nombre.endswith('.pdf'):
            lector = pypdf.PdfReader(archivo)
            for pagina in lector.pages:
                texto += pagina.extract_text() + "\n"
        elif nombre.endswith('.pptx'):
            presentacion = Presentation(archivo)
            for diapositiva in presentacion.slides:
                for forma in diapositiva.shapes:
                    if hasattr(forma, "text"):
                        texto += forma.text + "\n"
        elif nombre.endswith('.docx'):
            documento = docx.Document(archivo)
            for parrafo in documento.paragraphs:
                texto += parrafo.text + "\n"
        elif nombre.endswith('.xlsx'):
            libro = openpyxl.load_workbook(archivo, data_only=True)
            for hoja in libro.worksheets:
                for fila in hoja.iter_rows(values_only=True):
                    fila_texto = [str(celda) for celda in fila if celda is not None]
                    if fila_texto:
                        texto += " | ".join(fila_texto) + "\n"
        elif nombre.endswith('.m') or nombre.endswith('.py'):
            texto += archivo.getvalue().decode("utf-8") + "\n"
    except Exception as e:
        texto += f"[Error al extraer texto de este archivo: {e}]\n"
    return texto

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Rúbrica")
    opcion_rubrica = st.radio("¿Cómo vas a introducir la rúbrica?", ["Pegar texto", "Subir Archivo (PDF, Word, Excel)"])
    
    rubrica_texto = ""
    archivo_rubrica = None
    
    if opcion_rubrica == "Pegar texto":
        rubrica_texto = st.text_area("Pega aquí los criterios:", height=200)
    else:
        archivo_rubrica = st.file_uploader("Sube la rúbrica de evaluación", type=["pdf", "docx", "xlsx"], key="rubrica_file")

with col2:
    st.subheader("2. Trabajo del Alumno")
    archivos_alumno = st.file_uploader(
        "Sube los archivos (PDF, Word, PPT, Excel, MATLAB .m, Python .py)", 
        type=["pdf", "docx", "pptx", "xlsx", "m", "py"], 
        accept_multiple_files=True,
        key="alumno_archivos"
    )

if "resultado_evaluacion" not in st.session_state:
    st.session_state.resultado_evaluacion = None

if st.button("Evaluar Trabajo", type="primary"):
    if not api_key:
        st.error("Por favor, introduce tu API Key arriba.")
    elif opcion_rubrica == "Pegar texto" and not rubrica_texto:
        st.warning("Por favor, pega el texto de la rúbrica.")
    elif opcion_rubrica != "Pegar texto" and not archivo_rubrica:
        st.warning("Por favor, sube el archivo de la rúbrica.")
    elif not archivos_alumno:
        st.warning("Por favor, sube al menos un archivo del alumno.")
    else:
        st.info("Procesando archivos y analizando... (esto puede tardar unos segundos)")
        
        try:
            if opcion_rubrica == "Pegar texto":
                texto_rubrica_final = rubrica_texto
            else:
                texto_rubrica_final = extraer_texto_archivo(archivo_rubrica)
                
            texto_alumno_final = ""
            for archivo in archivos_alumno:
                texto_alumno_final += f"\n\n--- INICIO DEL ARCHIVO: {archivo.name} ---\n"
                texto_alumno_final += extraer_texto_archivo(archivo)
                texto_alumno_final += f"\n--- FIN DEL ARCHIVO: {archivo.name} ---\n"
            
            # --- NUEVO PROMPT SEPARANDO CÁLCULO DE REDACCIÓN ---
            instruccion_tono = ""
            if "Constructivo" in tono_evaluacion:
                instruccion_tono = "Tono de la justificación: Constructivo (explica cómo mejorar los fallos detectados)."
            elif "Estricto" in tono_evaluacion:
                instruccion_tono = "Tono de la justificación: Estricto (señala los errores de forma muy directa y cruda)."
            else:
                instruccion_tono = "Tono de la justificación: Breve (máximo una línea por criterio, muy resumido)."

            client = genai.Client(api_key=api_key)
            
            instrucciones = f"""
            Eres un profesor de ingeniería evaluando un proyecto.
            
            FASE 1: CÁLCULO ESTRICTO DE LA NOTA (REGLAS INMUTABLES)
            - Usa EXCLUSIVAMENTE la rúbrica proporcionada.
            - Evalúa TODOS Y CADA UNO de los criterios.
            - Sé extremadamente riguroso. Busca exhaustivamente cualquier fallo técnico o requisito omitido. Si falta algo, penaliza la nota.
            
            RÚBRICA:
            {texto_rubrica_final}
            
            TRABAJO DEL ALUMNO:
            {texto_alumno_final}
            
            FASE 2: REDACCIÓN DEL INFORME
            Aplica este estilo estrictamente a tus justificaciones:
            {instruccion_tono}
            
            ESTRUCTURA DE TU RESPUESTA:
            1. NOTA FINAL CALCULADA: (Suma de puntos / Suma de puntos máximos).
            2. DESGLOSE POR CRITERIO: 
            - Nombre del Criterio: [Puntos asignados] / [Máximo posible]
            - Justificación: [Aplicando el tono elegido en la Fase 2]
            """
            
# --- NUEVO: Sistema de Respaldo Automático (Fallback) ---
            modelos_a_probar = ['gemini-3.6-flash', 'gemini-1.5-flash']
            indice_modelo = 0
            
            intentos_maximos = 4
            for intento in range(intentos_maximos):
                modelo_actual = modelos_a_probar[indice_modelo]
                try:
                    response = client.models.generate_content(
                        model=modelo_actual,
                        contents=instrucciones,
                        config={'temperature': 0.2}
                    )
                    
                    st.session_state.resultado_evaluacion = response.text
                    break 
                    
                except Exception as error_ia:
                    if "503" in str(error_ia) or "429" in str(error_ia):
                        # Si falla el 3.6, pasamos al 1.5
                        if indice_modelo == 0:
                            indice_modelo = 1
                            st.warning(f"Modelo principal saturado. Cambiando automáticamente al modelo de respaldo (gemini-1.5-flash)...")
                            time.sleep(2)
                        # Si el 1.5 también falla y nos quedan intentos, esperamos
                        elif intento < (intentos_maximos - 1):
                            st.warning(f"Todos los modelos saturados. Reintentando en 15 segundos... (Intento {intento + 1} de {intentos_maximos})")
                            time.sleep(15)
                        else:
                            raise error_ia 
                    else:
                        raise error_ia 
            
        except Exception as e:
            st.error(f"Hubo un error al procesar los archivos: {e}")

# --- SECCIÓN DE DESCARGA EN WORD ---
if st.session_state.resultado_evaluacion:
    st.success("¡Evaluación completada!")
    st.write(st.session_state.resultado_evaluacion)
    
    # 1. Creamos un documento Word en blanco en la memoria
    doc = docx.Document()
    doc.add_heading('Informe de Evaluación Automatizada', 0)
    doc.add_paragraph(st.session_state.resultado_evaluacion)
    
    # 2. Lo guardamos en un "archivo virtual" (buffer)
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0) # Volvemos al principio del archivo para poder leerlo
    
    # 3. Botón de descarga apuntando al archivo Word
    st.download_button(
        label="📥 Descargar Informe en Word (.docx)",
        data=buffer,
        file_name="evaluacion_alumno.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        type="primary"
    )
