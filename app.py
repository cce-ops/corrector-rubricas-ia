import streamlit as st
from google import genai
import pypdf
import time
from pptx import Presentation
import docx
import openpyxl 

st.title("Corrector Automático por Rúbricas")
st.write("Herramienta de apoyo para la evaluación de proyectos de ingeniería.")
st.caption("🔒 Aviso de Privacidad: Los documentos subidos son procesados en memoria temporal y se eliminan al finalizar la evaluación. Se recomienda a los alumnos omitir datos personales sensibles.")

# Caja para la contraseña de la IA
api_key = st.text_input("Introduce tu API Key de Gemini:", type="password")

# --- NUEVO: Selector de Tono de Evaluación ---
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

# --- NUEVO: Memoria para guardar el resultado y poder descargarlo ---
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
            
            # --- NUEVO: Adaptamos el prompt según el tono elegido ---
            instruccion_tono = ""
            if "Constructivo" in tono_evaluacion:
                instruccion_tono = "Ofrece un feedback constructivo, explicando al alumno cómo puede mejorar en los puntos donde ha fallado."
            elif "Estricto" in tono_evaluacion:
                instruccion_tono = "Sé muy estricto y directo. Señala únicamente los errores técnicos y lo que falta, sin lenguaje suavizado."
            else:
                instruccion_tono = "Sé extremadamente breve. Da la nota y una sola frase de justificación por criterio, sin rodeos."

            client = genai.Client(api_key=api_key)
            
            instrucciones = f"""
            Eres un profesor de ingeniería. Tu tarea es evaluar el trabajo de un alumno compuesto por varios archivos.
            
            REGLAS OBLIGATORIAS:
            - Debes usar EXCLUSIVAMENTE la rúbrica proporcionada.
            - Evalúa TODOS los criterios. Si no hay mención a un criterio en los archivos, la nota es 0.
            - {instruccion_tono}
            
            RÚBRICA:
            {texto_rubrica_final}
            
            TRABAJO DEL ALUMNO:
            {texto_alumno_final}
            
            ESTRUCTURA DE TU RESPUESTA:
            1. NOTA FINAL CALCULADA: (Suma de puntos obtenidos / Suma de puntos máximos posibles).
            2. DESGLOSE POR CRITERIO: 
            - Nombre del Criterio: [Puntos asignados] / [Máximo posible]
            - Justificación: Según el estilo solicitado.
            """
            
            intentos_maximos = 3
            for intento in range(intentos_maximos):
                try:
                    response = client.models.generate_content(
                        model='gemini-3.6-flash',
                        contents=instrucciones
                    )
                    
                    # Guardamos el resultado en la memoria de la sesión
                    st.session_state.resultado_evaluacion = response.text
                    break 
                    
                except Exception as error_ia:
                    if "503" in str(error_ia) and intento < (intentos_maximos - 1):
                        st.warning(f"Reintentando en 5 segundos... (Intento {intento + 1} de {intentos_maximos})")
                        time.sleep(5)
                    else:
                        raise error_ia 
            
        except Exception as e:
            st.error(f"Hubo un error al procesar los archivos: {e}")

# --- NUEVO: Mostrar resultado y botón de descarga si hay datos en la memoria ---
if st.session_state.resultado_evaluacion:
    st.success("¡Evaluación completada!")
    st.write(st.session_state.resultado_evaluacion)
    
    # Botón mágico para descargar
    st.download_button(
        label="📥 Descargar Informe de Evaluación (.txt)",
        data=st.session_state.resultado_evaluacion,
        file_name="evaluacion_alumno.txt",
        mime="text/plain",
        type="primary"
    )
