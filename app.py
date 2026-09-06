import streamlit as st
from google import genai
import pypdf
import time  # Importamos 'time' para los reintentos automáticos

st.title("Corrector Automático por Rúbricas")
st.write("Herramienta de apoyo para la evaluación de proyectos de ingeniería.")

# Caja para la contraseña de la IA
api_key = st.text_input("Introduce tu API Key de Gemini:", type="password")

# Función auxiliar para leer PDFs y sacar el texto
def extraer_texto_pdf(archivo):
    lector = pypdf.PdfReader(archivo)
    texto = ""
    for pagina in lector.pages:
        texto += pagina.extract_text() + "\n"
    return texto

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Rúbrica")
    opcion_rubrica = st.radio("¿Cómo vas a introducir la rúbrica?", ["Pegar texto", "Subir PDF"])
    
    rubrica_texto = ""
    archivo_rubrica = None
    
    if opcion_rubrica == "Pegar texto":
        rubrica_texto = st.text_area("Pega aquí los criterios:", height=200)
    else:
        archivo_rubrica = st.file_uploader("Sube la rúbrica en PDF", type=["pdf"], key="rubrica_pdf")

with col2:
    st.subheader("2. Trabajo del Alumno (PDF)")
    archivo_alumno = st.file_uploader("Sube la memoria técnica", type=["pdf"], key="alumno_pdf")

if st.button("Evaluar Trabajo", type="primary"):
    # 1. Comprobamos que no falte nada antes de empezar
    if not api_key:
        st.error("Por favor, introduce tu API Key arriba para conectar con la IA.")
    elif opcion_rubrica == "Pegar texto" and not rubrica_texto:
        st.warning("Por favor, pega el texto de la rúbrica.")
    elif opcion_rubrica == "Subir PDF" and not archivo_rubrica:
        st.warning("Por favor, sube el archivo PDF de la rúbrica.")
    elif not archivo_alumno:
        st.warning("Por favor, sube el archivo PDF del alumno.")
    else:
        st.info("Procesando archivos y analizando... (esto puede tardar unos segundos)")
        
        try:
            # 2. Extraemos el texto de la rúbrica
            if opcion_rubrica == "Subir PDF":
                texto_rubrica_final = extraer_texto_pdf(archivo_rubrica)
            else:
                texto_rubrica_final = rubrica_texto
                
            # 3. Extraemos el texto del alumno
            texto_alumno_final = extraer_texto_pdf(archivo_alumno)
            
            # 4. Conectamos con la IA
            client = genai.Client(api_key=api_key)
            
            instrucciones = f"""
            Eres un profesor de ingeniería muy estricto. Tu tarea es evaluar el trabajo de un alumno.
            
            REGLAS OBLIGATORIAS:
            - Debes usar EXCLUSIVAMENTE la rúbrica proporcionada.
            - Debes evaluar TODOS Y CADA UNO de los criterios que aparezcan en la rúbrica. No puedes omitir ninguno.
            - Si el alumno no menciona nada sobre un criterio, su nota en ese criterio es 0.
            
            RÚBRICA:
            {texto_rubrica_final}
            
            TRABAJO DEL ALUMNO (Extraído del PDF):
            {texto_alumno_final}
            
            ESTRUCTURA DE TU RESPUESTA:
            1. NOTA FINAL CALCULADA: (Suma de puntos obtenidos / Suma de puntos máximos posibles de la rúbrica).
            2. DESGLOSE POR CRITERIO (Obligatorio evaluar cada uno): 
            - Nombre del Criterio: [Puntos asignados] / [Máximo posible]
            - Justificación DETALLADA: Cita qué ha hecho bien el alumno y qué elementos técnicos le han faltado explícitamente según la rúbrica.
            """
            
            # 5. Envío de datos con SISTEMA DE REINTENTOS ANTISATURACIÓN
            intentos_maximos = 3
            
            for intento in range(intentos_maximos):
                try:
                    response = client.models.generate_content(
                        model='gemini-3.6-flash',
                        contents=instrucciones
                    )
                    
                    # Si la IA responde bien, mostramos el resultado y salimos del bucle
                    st.success("¡Evaluación completada!")
                    st.write(response.text)
                    break 
                    
                except Exception as error_ia:
                    # Comprobamos si es el error 503 y si nos quedan intentos
                    if "503" in str(error_ia) and intento < (intentos_maximos - 1):
                        st.warning(f"Servidores de Google muy ocupados. Reintentando en 5 segundos... (Intento {intento + 1} de {intentos_maximos})")
                        time.sleep(5) # Espera 5 segundos antes de volver a preguntar
                    else:
                        # Si es otro error o se acabaron los intentos, lanzamos el error definitivo
                        raise error_ia 
            
        except Exception as e:
            st.error(f"Hubo un error al procesar el archivo o conectar con la IA: {e}")
