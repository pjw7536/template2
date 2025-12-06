const IonBombardLogo = ({ className }) => (
    <svg
        className={className}
        width="220"
        height="80"
        viewBox="0 0 220 80"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
    >
        {/* === ICON: Ion Bombardment === */}
        <g transform="translate(10, 10)">
            {/* Wafer Surface */}
            <line x1="10" y1="50" x2="70" y2="50" />

            {/* Ion Trajectories (Diagonal beams converging to impact point) */}
            <line x1="18" y1="10" x2="38" y2="40" />
            <line x1="40" y1="8" x2="40" y2="40" />
            <line x1="62" y1="10" x2="42" y2="40" />

            {/* Ion Heads (circles near the top of each trajectory) */}
            <circle cx="18" cy="10" r="2.5" />
            <circle cx="40" cy="8" r="2.5" />
            <circle cx="62" cy="10" r="2.5" />

            {/* Impact Spark (center of bombardment) */}
            <circle cx="40" cy="50" r="4" />

            {/* Small spark lines */}
            <line x1="40" y1="44" x2="40" y2="40" />
            <line x1="34" y1="50" x2="30" y2="50" />
            <line x1="46" y1="50" x2="50" y2="50" />
            <line x1="36" y1="46" x2="32" y2="42" />
            <line x1="44" y1="46" x2="48" y2="42" />
        </g>

        {/* === TEXT: Etch AX Portal === */}
        <g transform="translate(90, 20)">
            {/* Main brand (AX) */}
            <text
                x="0"
                y="25"
                fontFamily="Inter, system-ui, -apple-system, BlinkMacSystemFont, sans-serif"
                fontSize="26"
                fontWeight="700"
            >
                Etch AX
            </text>

            {/* Sub brand (Portal) */}
            <text
                x="0"
                y="45"
                fontFamily="Inter, system-ui, -apple-system, BlinkMacSystemFont, sans-serif"
                fontSize="16"
                fontWeight="400"
                opacity="0.7"
            >
                Portal
            </text>
        </g>
    </svg>
)

export default IonBombardLogo
