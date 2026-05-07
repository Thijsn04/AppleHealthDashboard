import json
import streamlit.components.v1 as components

def render_body_map(selected_regions=None):
    """
    Renders an interactive SVG body map. Pre-highlights `selected_regions`.
    """
    if selected_regions is None:
        selected_regions = []

    selected_json = json.dumps(selected_regions)

    svg_body = f"""
    <div id="body-map-container" style="display: flex; justify-content: center; gap: 40px; padding: 20px;">
        <div class="body-view">
            <h4 style="text-align: center; color: #94A3B8; font-family: sans-serif;">Front</h4>
            <svg width="200" height="400" viewBox="0 0 200 400">
                <!-- Head -->
                <circle cx="100" cy="40" r="25" class="region" data-region="Head" fill="#1E293B" stroke="#334155" />
                <!-- Torso -->
                <rect x="70" y="70" width="60" height="100" rx="10" class="region" data-region="Torso" fill="#1E293B" stroke="#334155" />
                <!-- Arms -->
                <rect x="40" y="75" width="25" height="120" rx="12" class="region" data-region="Left Arm" fill="#1E293B" stroke="#334155" />
                <rect x="135" y="75" width="25" height="120" rx="12" class="region" data-region="Right Arm" fill="#1E293B" stroke="#334155" />
                <!-- Legs -->
                <rect x="72" y="175" width="25" height="180" rx="12" class="region" data-region="Left Leg" fill="#1E293B" stroke="#334155" />
                <rect x="103" y="175" width="25" height="180" rx="12" class="region" data-region="Right Leg" fill="#1E293B" stroke="#334155" />
            </svg>
        </div>
    </div>

    <style>
        .region {{ transition: all 0.3s ease; cursor: pointer; }}
        .region:hover {{ fill: #10B981; stroke: #34D399; opacity: 0.8; }}
        .region.active {{ fill: #10B981; stroke: #34D399; }}
        #tooltip {{
            position: absolute; background: rgba(15, 23, 42, 0.9); color: white;
            padding: 8px 12px; border-radius: 6px; font-family: sans-serif;
            font-size: 12px; pointer-events: none; opacity: 0; transition: opacity 0.2s;
            border: 1px solid rgba(255,255,255,0.1);
        }}
    </style>

    <div id="tooltip"></div>

    <script>
        const regions = document.querySelectorAll('.region');
        const tooltip = document.getElementById('tooltip');
        const preSelected = {selected_json};

        regions.forEach(r => {{
            const name = r.getAttribute('data-region');

            if (preSelected.includes(name)) {{
                r.classList.add('active');
            }}

            r.addEventListener('mouseenter', (e) => {{
                tooltip.style.opacity = 1;
                tooltip.innerText = name;
            }});

            r.addEventListener('mousemove', (e) => {{
                tooltip.style.left = (e.pageX + 10) + 'px';
                tooltip.style.top = (e.pageY + 10) + 'px';
            }});

            r.addEventListener('mouseleave', () => {{
                tooltip.style.opacity = 0;
            }});

            r.addEventListener('click', () => {{
                r.classList.toggle('active');
            }});
        }});
    </script>
    """

    components.html(svg_body, height=450)
